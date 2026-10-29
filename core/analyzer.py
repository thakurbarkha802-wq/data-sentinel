"""DataSentinel Quality Analyzer

Core data quality analysis engine that audits tabular CSV data across completeness,
validity, and uniqueness dimensions, producing structured, transparent reports.
"""

from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple, Union

from .loader import FileReadResult, deduplicate_headers, load_csv, load_csv_from_stream
from .models import ColumnSummary, DimensionScores, QualityIssue, QualityReport
from .rules import ColumnRule


class DataSentinel:
    """Configurable data quality analyzer for CSV datasets."""

    def __init__(self, rules: Optional[Dict[str, ColumnRule]] = None):
        """Initializes DataSentinel with optional column validation rules.
        
        Args:
            rules: Dictionary mapping column names to their ColumnRule.
        """
        self.rules: Dict[str, ColumnRule] = rules or {}

    def add_rule(self, rule: ColumnRule) -> None:
        """Adds or updates a column validation rule."""
        self.rules[rule.column] = rule

    def analyze_file(self, file_path: Union[str, Path]) -> QualityReport:
        """Loads and audits a CSV file from disk.
        
        Args:
            file_path: Path to the target CSV file.
            
        Returns:
            QualityReport containing metrics, dimension scores, and findings.
        """
        parsed = load_csv(file_path)
        return self._analyze_parsed(parsed)

    def analyze_stream(self, stream: TextIO, file_path: str = "<in-memory>") -> QualityReport:
        """Audits a readable CSV text stream directly without disk persistence.
        
        Args:
            stream: A readable text stream (e.g. io.StringIO or text file).
            file_path: Identifier or display name for the dataset.
            
        Returns:
            QualityReport containing metrics, dimension scores, and findings.
        """
        parsed = load_csv_from_stream(stream, file_path=file_path)
        return self._analyze_parsed(parsed)

    def analyze_data(
        self,
        headers: List[str],
        rows: List[List[str]],
        file_path: str = "<in-memory>",
    ) -> QualityReport:
        """Audits in-memory CSV headers and rows (useful for tests and pipelines).
        
        Args:
            headers: List of column header names.
            rows: List of string rows.
            file_path: Identifier name for the dataset.
            
        Returns:
            QualityReport containing metrics, dimension scores, and findings.
        """
        # Deduplicate headers if raw headers contain duplicate names
        deduped_headers, header_issues = deduplicate_headers(headers)
        # Form (line_number, row) pairs, header is line 1, data starts at line 2
        indexed_rows = [(idx + 2, row) for idx, row in enumerate(rows)]
        parsed = FileReadResult(
            file_path=file_path,
            headers=deduped_headers,
            rows=indexed_rows,
            issues=header_issues,
            is_empty=(len(indexed_rows) == 0 or len(deduped_headers) == 0),
        )
        return self._analyze_parsed(parsed)

    def _analyze_parsed(self, parsed: FileReadResult) -> QualityReport:
        """Internal analysis engine operating on FileReadResult."""
        report = QualityReport(
            file_path=parsed.file_path,
            total_columns=len(parsed.headers),
            column_names=list(parsed.headers),
        )

        # Include any structural warnings recorded during file loading (e.g. malformed rows)
        report.issues.extend(parsed.issues)

        # Handle empty dataset edge case (zero data rows or zero headers)
        if parsed.is_empty or len(parsed.rows) == 0 or len(parsed.headers) == 0:
            report.total_rows = 0
            report.scores = DimensionScores(
                completeness=0.0,
                validity=0.0,
                uniqueness=0.0,
                overall=0.0,
            )
            # Create empty column summaries if headers exist
            for col in parsed.headers:
                rule_desc = self.rules[col].describe() if col in self.rules else None
                report.column_summaries[col] = ColumnSummary(
                    name=col,
                    total_cells=0,
                    missing_count=0,
                    invalid_count=0,
                    rule_description=rule_desc,
                )
            return report

        total_rows = len(parsed.rows)
        report.total_rows = total_rows
        headers = parsed.headers
        total_cells = total_rows * len(headers)

        # Initialize column summaries
        col_summaries: Dict[str, ColumnSummary] = {}
        for col in headers:
            rule_desc = self.rules[col].describe() if col in self.rules else None
            col_summaries[col] = ColumnSummary(
                name=col,
                total_cells=total_rows,
                missing_count=0,
                invalid_count=0,
                rule_description=rule_desc,
            )

        # 1. Uniqueness check (detect exact duplicate rows)
        # Tracks record tuple -> first seen CSV line number
        seen_records: Dict[Tuple[str, ...], int] = {}
        duplicate_row_numbers: List[int] = []
        duplicate_count = 0

        for line_no, row in parsed.rows:
            record_tuple = tuple(row)
            if record_tuple in seen_records:
                duplicate_count += 1
                duplicate_row_numbers.append(line_no)
                first_line = seen_records[record_tuple]
                report.issues.append(
                    QualityIssue(
                        issue_type="duplicate_row",
                        row_number=line_no,
                        message=f"Duplicate record: identical to row {first_line}.",
                        value=dict(zip(headers, row)),
                    )
                )
            else:
                seen_records[record_tuple] = line_no

        report.duplicate_rows_count = duplicate_count
        report.duplicate_row_numbers = duplicate_row_numbers

        # 2. Completeness & Validity checks (cell-by-cell)
        missing_count = 0
        invalid_count = 0
        evaluated_cells_count = 0  # Non-blank cells belonging to columns with rules

        for line_no, row in parsed.rows:
            for idx, col_name in enumerate(headers):
                cell_value = row[idx] if idx < len(row) else ""
                
                # Check for missing / blank values across all columns
                if cell_value is None or str(cell_value).strip() == "":
                    missing_count += 1
                    col_summaries[col_name].missing_count += 1
                    report.issues.append(
                        QualityIssue(
                            issue_type="missing_value",
                            row_number=line_no,
                            column=col_name,
                            message=f"Column '{col_name}' has a missing or blank value.",
                            value=cell_value,
                        )
                    )
                else:
                    # Value is present, check if column has a configured validation rule
                    if col_name in self.rules:
                        rule = self.rules[col_name]
                        if getattr(rule, "is_constrained", True):
                            evaluated_cells_count += 1
                            is_valid, failure_reason = rule.validate(cell_value)

                            if not is_valid:
                                invalid_count += 1
                                col_summaries[col_name].invalid_count += 1
                                report.issues.append(
                                    QualityIssue(
                                        issue_type="invalid_value",
                                        row_number=line_no,
                                        column=col_name,
                                        message=failure_reason or f"Invalid value in '{col_name}'",
                                        value=cell_value,
                                    )
                                )

        report.missing_values_count = missing_count
        report.invalid_values_count = invalid_count
        report.column_summaries = col_summaries

        # 3. Transparent Quality Dimension Scoring
        # Completeness: Ratio of populated cells to total expected grid cells
        if total_cells > 0:
            completeness = round(((total_cells - missing_count) / total_cells) * 100, 2)
        else:
            completeness = 0.0
        completeness = max(0.0, min(100.0, completeness))

        # Uniqueness: Ratio of non-duplicate rows to total rows
        if total_rows > 0:
            uniqueness = round(((total_rows - duplicate_count) / total_rows) * 100, 2)
        else:
            uniqueness = 0.0
        uniqueness = max(0.0, min(100.0, uniqueness))

        # Validity: Ratio of rule-passing cells to evaluated rule-constrained cells
        if evaluated_cells_count > 0:
            validity = round(((evaluated_cells_count - invalid_count) / evaluated_cells_count) * 100, 2)
        else:
            # If no rules were configured for any column, all present data passes by default
            validity = 100.0
        validity = max(0.0, min(100.0, validity))

        # Weighted Overall Score: 35% Completeness, 35% Validity, 30% Uniqueness
        overall = round((0.35 * completeness) + (0.35 * validity) + (0.30 * uniqueness), 2)
        overall = max(0.0, min(100.0, overall))

        report.scores = DimensionScores(
            completeness=completeness,
            validity=validity,
            uniqueness=uniqueness,
            overall=overall,
        )

        return report

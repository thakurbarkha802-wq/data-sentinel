"""DataSentinel Safe CSV Loader

Safely reads CSV files with utf-8-sig encoding, robustly handles empty files,
missing headers, duplicate columns, malformed rows, and raises user-friendly errors.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, TextIO, Tuple, Union

from .models import QualityIssue


class DataSentinelError(Exception):
    """Base exception for user-facing DataSentinel errors."""
    pass


@dataclass
class FileReadResult:
    """Represents the raw parsed content of a CSV file."""
    file_path: str
    headers: List[str] = field(default_factory=list)
    # List of (csv_line_number, row_values)
    rows: List[Tuple[int, List[str]]] = field(default_factory=list)
    issues: List[QualityIssue] = field(default_factory=list)
    is_empty: bool = False


def deduplicate_headers(raw_headers: List[str]) -> Tuple[List[str], List[QualityIssue]]:
    """Deduplicates column header names while preserving order and emitting schema warnings.
    
    If headers are ['name', 'age', 'name'], they are disambiguated as ['name', 'age', 'name_2'].
    If empty headers exist like ['', 'age'], they are disambiguated as ['Unnamed_1', 'age'].
    """
    seen_counts: dict[str, int] = {}
    used_names: set[str] = set()
    deduped: List[str] = []
    issues: List[QualityIssue] = []

    for idx, raw_h in enumerate(raw_headers):
        base = raw_h if raw_h != "" else f"Unnamed_{idx + 1}"
        if base in seen_counts:
            seen_counts[base] += 1
            candidate = f"{base}_{seen_counts[base]}"
            while candidate in used_names:
                seen_counts[base] += 1
                candidate = f"{base}_{seen_counts[base]}"
            
            issues.append(
                QualityIssue(
                    issue_type="schema_warning",
                    column=base,
                    row_number=1,
                    message=f"Duplicate column name '{base}' in CSV header. Disambiguated as '{candidate}'.",
                )
            )
            deduped.append(candidate)
            used_names.add(candidate)
        else:
            seen_counts[base] = 1
            if base != raw_h:
                issues.append(
                    QualityIssue(
                        issue_type="schema_warning",
                        column=base,
                        row_number=1,
                        message=f"Empty column name at column index {idx + 1}. Disambiguated as '{base}'.",
                    )
                )
            deduped.append(base)
            used_names.add(base)

    return deduped, issues


def load_csv_from_stream(stream: TextIO, file_path: str = "<in-memory>") -> FileReadResult:
    """Safely loads and parses CSV data directly from a text stream.
    
    Args:
        stream: A readable text stream (e.g. io.StringIO or an open file).
        file_path: Identifier or display name for the dataset.
        
    Returns:
        FileReadResult with parsed headers, rows (with 1-indexed line numbers),
        and any structural parsing warnings.
    """
    reader = csv.reader(stream)
    
    # Read first line as header
    first_line = None
    try:
        first_line = next(reader)
    except StopIteration:
        # Stream is completely empty
        return FileReadResult(
            file_path=file_path,
            is_empty=True,
            issues=[
                QualityIssue(
                    issue_type="schema_warning",
                    message="The CSV file is completely empty.",
                )
            ],
        )

    # Strip whitespace from header names and check for empty file with blank line
    raw_headers = [h.strip() for h in first_line]
    if not raw_headers or all(h == "" for h in raw_headers):
        return FileReadResult(
            file_path=file_path,
            is_empty=True,
            issues=[
                QualityIssue(
                    issue_type="schema_warning",
                    message="The CSV file has no valid column headers.",
                )
            ],
        )

    # Disambiguate duplicate or empty column headers
    headers, issues = deduplicate_headers(raw_headers)

    # Read data rows using physical line number tracking
    parsed_rows: List[Tuple[int, List[str]]] = []
    prev_line_num = reader.line_num

    for row in reader:
        start_line = prev_line_num + 1
        end_line = reader.line_num
        prev_line_num = end_line

        # Distinguish truly blank physical lines from malformed records
        is_blank_line = (
            len(row) == 0
            or (len(row) == 1 and row[0].strip() == "" and len(headers) > 1)
            or (len(headers) == 1 and len(row) == 1 and row[0] == "")
        )
        if is_blank_line:
            # Do not synthesize fake records for blank physical lines
            continue

        # Check for row length mismatch (malformed row)
        if len(row) != len(headers):
            issues.append(
                QualityIssue(
                    issue_type="malformed_row",
                    row_number=start_line,
                    message=(
                        f"Row has {len(row)} columns, expected {len(headers)} "
                        f"(matching header)."
                    ),
                )
            )
            # Normalize row length to avoid indexing crashes during validation
            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            else:
                row = row[:len(headers)]

        parsed_rows.append((start_line, row))

    is_empty = len(parsed_rows) == 0
    if is_empty:
        issues.append(
            QualityIssue(
                issue_type="schema_warning",
                message="CSV contains column headers but zero data rows.",
            )
        )

    return FileReadResult(
        file_path=file_path,
        headers=headers,
        rows=parsed_rows,
        issues=issues,
        is_empty=is_empty,
    )


def load_csv(file_path: Union[str, Path]) -> FileReadResult:
    """Safely loads and parses a CSV file with robust error handling.
    
    Args:
        file_path: Path to the target CSV file.
        
    Returns:
        FileReadResult with parsed headers, rows (with 1-indexed line numbers),
        and any structural parsing warnings.
        
    Raises:
        DataSentinelError: When file is missing, inaccessible, or cannot be parsed.
    """
    path = Path(file_path)

    if not path.exists():
        raise DataSentinelError(f"Target file does not exist: '{path}'")

    if path.is_dir():
        raise DataSentinelError(f"Path is a directory, not a CSV file: '{path}'")

    # Read using utf-8-sig to automatically handle and strip UTF-8 BOM if present
    try:
        with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
            return load_csv_from_stream(f, file_path=str(path))
    except PermissionError:
        raise DataSentinelError(f"Permission denied accessing file: '{path}'")
    except UnicodeDecodeError as e:
        raise DataSentinelError(
            f"File encoding error while reading '{path}': {e}. "
            "Please ensure the file is saved with UTF-8 encoding."
        )
    except Exception as e:
        raise DataSentinelError(f"Unexpected error reading '{path}': {e}")

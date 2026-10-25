"""DataSentinel Core Models

Defines structured dataclasses for issues, column summaries, dimension scores,
and comprehensive quality reports.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class QualityIssue:
    """Represents a single data quality finding."""
    issue_type: str  # "missing_value", "invalid_type", "range_violation", "duplicate_row", "malformed_row", "schema_warning"
    message: str
    row_number: Optional[int] = None  # 1-indexed CSV line number (header is line 1, data starts line 2)
    column: Optional[str] = None
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        val = self.value
        if val is not None and not isinstance(val, (dict, list, int, float, bool, str)):
            val = str(val)
        return {
            "issue_type": self.issue_type,
            "message": self.message,
            "row_number": self.row_number,
            "column": self.column,
            "value": val,
        }


@dataclass
class ColumnSummary:
    """Summary metrics for an individual column."""
    name: str
    total_cells: int = 0
    missing_count: int = 0
    invalid_count: int = 0
    rule_description: Optional[str] = None

    @property
    def completeness_score(self) -> float:
        if self.total_cells == 0:
            return 0.0
        score = ((self.total_cells - self.missing_count) / self.total_cells) * 100
        return max(0.0, min(100.0, round(score, 2)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_cells": self.total_cells,
            "missing_count": self.missing_count,
            "invalid_count": self.invalid_count,
            "completeness_score": self.completeness_score,
            "rule_description": self.rule_description,
        }


@dataclass
class DimensionScores:
    """Transparent quality dimension scores (0.0 - 100.0) and weighted overall score."""
    completeness: float = 0.0
    validity: float = 0.0
    uniqueness: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "completeness": self.completeness,
            "validity": self.validity,
            "uniqueness": self.uniqueness,
            "overall": self.overall,
        }


@dataclass
class QualityReport:
    """Comprehensive quality evaluation report for a dataset."""
    file_path: str
    total_rows: int = 0
    total_columns: int = 0
    column_names: list[str] = field(default_factory=list)
    duplicate_rows_count: int = 0
    duplicate_row_numbers: list[int] = field(default_factory=list)
    missing_values_count: int = 0
    invalid_values_count: int = 0
    scores: DimensionScores = field(default_factory=DimensionScores)
    column_summaries: dict[str, ColumnSummary] = field(default_factory=dict)
    issues: list[QualityIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "column_names": self.column_names,
            "duplicate_rows_count": self.duplicate_rows_count,
            "duplicate_row_numbers": self.duplicate_row_numbers,
            "missing_values_count": self.missing_values_count,
            "invalid_values_count": self.invalid_values_count,
            "scores": self.scores.to_dict(),
            "columns": {k: v.to_dict() for k, v in self.column_summaries.items()},
            "issues": [issue.to_dict() for issue in self.issues],
        }

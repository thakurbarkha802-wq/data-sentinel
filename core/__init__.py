"""DataSentinel Core Package

A lightweight, reliable, and transparent data quality engine for tabular CSV data.
"""

from .models import DimensionScores, QualityReport, ColumnSummary, QualityIssue
from .rules import ColumnRule
from .loader import load_csv, load_csv_from_stream, DataSentinelError, FileReadResult, deduplicate_headers
from .analyzer import DataSentinel
from .export import serialize_report, report_to_json

__all__ = [
    "DataSentinel",
    "ColumnRule",
    "QualityReport",
    "DimensionScores",
    "ColumnSummary",
    "QualityIssue",
    "load_csv",
    "load_csv_from_stream",
    "deduplicate_headers",
    "DataSentinelError",
    "FileReadResult",
    "serialize_report",
    "report_to_json",
]

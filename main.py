"""DataSentinel CLI Entry Point

Executes data quality audits on CSV files and renders clean, structured terminal reports.
"""

import sys
from pathlib import Path
from typing import Optional

from core.analyzer import DataSentinel
from core.loader import DataSentinelError
from core.models import QualityReport
from core.rules import ColumnRule


def render_score_bar(score: float, width: int = 20) -> str:
    """Renders a visual ASCII progress bar for scores between 0 and 100."""
    filled = int(round((score / 100.0) * width))
    filled = max(0, min(width, filled))
    bar = "=" * filled + " " * (width - filled)
    return f"[{bar}] {score:5.1f}%"


def print_cli_report(report: QualityReport) -> None:
    """Prints a structured, user-friendly quality report to stdout."""
    print("=" * 64)
    print("            DATA SENTINEL -- DATA QUALITY AUDIT")
    print("=" * 64)
    print(f"Target File:        {report.file_path}")
    print(f"Total Rows:         {report.total_rows}")
    print(f"Total Columns:      {report.total_columns}")
    if report.column_names:
        print(f"Columns:            {', '.join(report.column_names)}")
    print("-" * 64)
    print("DIMENSION SCORES (Weighted: 35% Comp | 35% Val | 30% Uniq)")
    print("-" * 64)
    print(f"Completeness:       {render_score_bar(report.scores.completeness)} ({report.missing_values_count} missing cells)")
    print(f"Validity:           {render_score_bar(report.scores.validity)} ({report.invalid_values_count} invalid values)")
    print(f"Uniqueness:         {render_score_bar(report.scores.uniqueness)} ({report.duplicate_rows_count} duplicate rows)")
    print("-" * 64)
    overall_bar = render_score_bar(report.scores.overall)
    print(f"OVERALL DQ SCORE:   {overall_bar.replace('%', ' / 100')}")
    print("=" * 64)

    # Column breakdown
    if report.column_summaries:
        print("\nCOLUMN-LEVEL METRICS:")
        print("-" * 64)
        for col_name, summary in report.column_summaries.items():
            rule_text = f"Rule: {summary.rule_description}" if summary.rule_description else "Unconstrained"
            status_text = f"invalid: {summary.invalid_count}" if summary.invalid_count > 0 else "valid"
            print(
                f"- {col_name:<15} | {summary.total_cells} cells | "
                f"missing: {summary.missing_count} ({summary.completeness_score}% complete) | "
                f"{status_text} | {rule_text}"
            )

    # Issues breakdown
    print("\nFINDINGS & ISSUES DETECTED:")
    print("-" * 64)
    if not report.issues:
        print("[OK] No quality issues found. All records meet configured criteria.")
    else:
        for idx, issue in enumerate(report.issues, 1):
            row_str = f"Row {issue.row_number}" if issue.row_number is not None else "Dataset"
            col_str = f" [{issue.column}]" if issue.column else ""
            print(f"{idx:2d}. [{row_str}]{col_str} ({issue.issue_type.upper()}): {issue.message}")
    print("=" * 64)


def main(file_arg: Optional[str] = None) -> int:
    """Main CLI execution flow."""
    # Determine target file path
    if file_arg:
        target_path = Path(file_arg)
    else:
        # Default to sample.csv in current directory or script's directory
        default_file = Path("sample.csv")
        if default_file.exists():
            target_path = default_file
        else:
            target_path = Path(__file__).resolve().parent / "sample.csv"

    # Configure validation rules
    # Note: Column rules are modular and configurable. We configure an age rule for sample datasets.
    rules = {
        "age": ColumnRule(
            column="age",
            data_type="int",
            min_value=0,
            max_value=120,
        )
    }

    analyzer = DataSentinel(rules=rules)

    try:
        report = analyzer.analyze_file(target_path)
        print_cli_report(report)
        return 0
    except DataSentinelError as e:
        print(f"\n[DataSentinel Error] {e}\n", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[Unexpected Error] An error occurred while processing: {e}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    cli_arg = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(cli_arg))
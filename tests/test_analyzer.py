"""Unit and integration tests for DataSentinel Analyzer and CLI
"""

import tempfile
import unittest
from pathlib import Path

from core.analyzer import DataSentinel
from core.rules import ColumnRule
import main


class TestDataSentinelAnalyzer(unittest.TestCase):
    """End-to-end tests for analyzer with existing sample and synthetic datasets."""

    def test_existing_sample_csv_audit(self):
        """Audits the existing sample.csv and verifies exact findings and scores."""
        sample_path = Path(__file__).resolve().parent.parent / "sample.csv"
        self.assertTrue(sample_path.exists(), "sample.csv must exist in the project")

        analyzer = DataSentinel(
            rules={"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=120)}
        )
        report = analyzer.analyze_file(sample_path)

        # Dataset metrics
        self.assertEqual(report.total_rows, 5)
        self.assertEqual(report.total_columns, 3)
        self.assertEqual(report.column_names, ["name", "age", "city"])

        # Quality findings
        self.assertEqual(report.missing_values_count, 0)
        self.assertEqual(report.duplicate_rows_count, 1)
        self.assertEqual(report.duplicate_row_numbers, [4])  # Line 4 is identical to Line 2
        self.assertEqual(report.invalid_values_count, 1)     # Line 5 has age = -5

        # Scores
        # Total cells = 15. Missing = 0 -> 100.0%
        # Total rows = 5. Duplicates = 1 -> 80.0%
        # Evaluated cells in 'age' = 5. Invalid = 1 -> 80.0%
        # Overall = 0.35*100.0 + 0.35*80.0 + 0.30*80.0 = 35.0 + 28.0 + 24.0 = 87.0
        self.assertEqual(report.scores.completeness, 100.0)
        self.assertEqual(report.scores.validity, 80.0)
        self.assertEqual(report.scores.uniqueness, 80.0)
        self.assertEqual(report.scores.overall, 87.0)

    def test_dataset_with_different_column_names(self):
        """Verifies that the engine generalizes to arbitrary domains and schemas."""
        headers = ["sku", "category", "price", "stock_qty"]
        rows = [
            ["SKU-001", "Electronics", "299.99", "15"],
            ["SKU-002", "Books", "19.50", "120"],
            ["SKU-003", "Clothing", "invalid_price", "0"],
        ]
        analyzer = DataSentinel(
            rules={
                "price": ColumnRule(column="price", data_type="float", min_value=0.01),
                "stock_qty": ColumnRule(column="stock_qty", data_type="int", min_value=0),
            }
        )
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.total_rows, 3)
        self.assertEqual(report.total_columns, 4)
        self.assertEqual(report.invalid_values_count, 1)
        # Invalid value is in 'price' at row 3 (line 4)
        invalid_issues = [i for i in report.issues if i.issue_type == "invalid_value"]
        self.assertEqual(len(invalid_issues), 1)
        self.assertEqual(invalid_issues[0].column, "price")
        self.assertEqual(invalid_issues[0].row_number, 4)

    def test_whitespace_cells_detected_across_all_columns(self):
        """Verifies that blank or whitespace-only cells in ANY column are flagged as missing."""
        headers = ["name", "email", "phone"]
        rows = [
            ["Alice", "alice@example.com", "1234567890"],
            ["  ", "bob@example.com", "0987654321"],
            ["Charlie", "", "5555555555"],
            ["Diana", "diana@example.com", "   "],
        ]
        analyzer = DataSentinel()
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.missing_values_count, 3)
        missing_columns = [i.column for i in report.issues if i.issue_type == "missing_value"]
        self.assertIn("name", missing_columns)
        self.assertIn("email", missing_columns)
        self.assertIn("phone", missing_columns)

    def test_cli_main_execution(self):
        """Verifies main.py CLI execution returns status code 0 on existing sample."""
        sample_path = Path(__file__).resolve().parent.parent / "sample.csv"
        exit_code = main.main(str(sample_path))
        self.assertEqual(exit_code, 0)

    def test_cli_main_non_existent_file(self):
        """Verifies main.py handles missing files cleanly without crashing."""
        exit_code = main.main("non_existent_dataset_random.csv")
        self.assertEqual(exit_code, 1)

    def test_empty_and_header_only_files_via_analyzer(self):
        """Verifies analyze_file returns 0.0 scores for empty files and header-only files."""
        # 1. 0-byte file
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as tmp:
            p_empty = Path(tmp.name)
        try:
            analyzer = DataSentinel()
            report_empty = analyzer.analyze_file(p_empty)
            self.assertEqual(report_empty.total_rows, 0)
            self.assertEqual(report_empty.scores.overall, 0.0)
            self.assertTrue(any(i.issue_type == "schema_warning" for i in report_empty.issues))
        finally:
            p_empty.unlink(missing_ok=True)

        # 2. Header-only file
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write("col_x,col_y\n")
            p_headers = Path(tmp.name)
        try:
            analyzer = DataSentinel()
            report_headers = analyzer.analyze_file(p_headers)
            self.assertEqual(report_headers.total_rows, 0)
            self.assertEqual(report_headers.total_columns, 2)
            self.assertEqual(report_headers.scores.overall, 0.0)
            self.assertTrue(any(i.issue_type == "schema_warning" for i in report_headers.issues))
        finally:
            p_headers.unlink(missing_ok=True)

    def test_csv_with_blank_lines_preserves_expected_metrics(self):
        """CSV with blank lines between records should not count blank lines as rows or missing cells."""
        content = "name,age\nAlice,25\n\nBob,30\n\n\nCharlie,35\n\n"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            tmp.write(content)
            p = Path(tmp.name)
        try:
            analyzer = DataSentinel(
                rules={"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=120)}
            )
            report = analyzer.analyze_file(p)
            self.assertEqual(report.total_rows, 3)
            self.assertEqual(report.missing_values_count, 0)
            self.assertEqual(report.scores.completeness, 100.0)
            self.assertEqual(report.scores.validity, 100.0)
            self.assertEqual(report.scores.uniqueness, 100.0)
            self.assertEqual(report.scores.overall, 100.0)
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

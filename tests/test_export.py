"""Unit tests for DataSentinel Export and Serialization Helpers
"""

import json
import unittest
from pathlib import Path

from core.analyzer import DataSentinel
from core.export import report_to_json, sanitize_file_path, serialize_report
from core.models import QualityIssue, QualityReport
from core.rules import ColumnRule


class TestExportHelpers(unittest.TestCase):
    """Tests path sanitization, dictionary serialization, and JSON report generation."""

    def test_sanitize_file_path(self):
        # Local Windows path should be stripped of directory components
        win_path = r"C:\Users\username\Documents\Data sentinel\sensitive\private_dataset.csv"
        self.assertEqual(sanitize_file_path(win_path), "private_dataset.csv")

        # POSIX style path
        posix_path = "/tmp/scratch_dir/upload_12345.csv"
        self.assertEqual(sanitize_file_path(posix_path), "upload_12345.csv")

        # Display name override takes precedence
        self.assertEqual(sanitize_file_path(win_path, display_name="client_audit.csv"), "client_audit.csv")

        # In-memory marker preserved
        self.assertEqual(sanitize_file_path("<in-memory>"), "<in-memory>")

    def test_serialize_report(self):
        analyzer = DataSentinel(
            rules={"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=120)}
        )
        report = analyzer.analyze_data(
            headers=["name", "age"],
            rows=[["Aman", "20"], ["Riya", "-5"]],
            file_path=r"C:\Secret\Path\users.csv",
        )

        data = serialize_report(report, display_name="users_clean.csv")

        self.assertIsInstance(data, dict)
        self.assertEqual(data["file_path"], "users_clean.csv")
        self.assertEqual(data["total_rows"], 2)
        self.assertEqual(data["total_columns"], 2)
        self.assertEqual(data["scores"]["completeness"], 100.0)
        self.assertEqual(data["scores"]["validity"], 50.0)
        self.assertEqual(len(data["issues"]), 1)
        self.assertEqual(data["issues"][0]["column"], "age")
        self.assertEqual(data["issues"][0]["issue_type"], "invalid_value")

    def test_report_to_json_validity(self):
        analyzer = DataSentinel()
        report = analyzer.analyze_data(
            headers=["name", "city"],
            rows=[["Aman", "Delhi"], ["Aman", "Delhi"]],
            file_path="sample.csv",
        )

        json_str = report_to_json(report)
        self.assertIsInstance(json_str, str)

        parsed = json.loads(json_str)
        self.assertEqual(parsed["file_path"], "sample.csv")
        self.assertEqual(parsed["duplicate_rows_count"], 1)
        self.assertEqual(parsed["scores"]["uniqueness"], 50.0)

    def test_report_to_json_with_unicode(self):
        analyzer = DataSentinel(
            rules={"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=100)}
        )
        report = analyzer.analyze_data(
            headers=["prénom", "age"],
            rows=[["Álvaro", "20"], ["Álvaro", "-5"]],
        )

        json_str = report_to_json(report, display_name="unicode.csv")
        # ensure_ascii=False should keep non-ASCII characters in column names and issue messages
        self.assertIn("prénom", json_str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["total_rows"], 2)
        self.assertIn("prénom", parsed["column_names"])
        self.assertEqual(len(parsed["issues"]), 1)

    def test_structured_issue_values_preserved_in_json(self):
        """Structured values (like duplicate row dicts) must serialize as native JSON objects, not Python strings."""
        analyzer = DataSentinel()
        report = analyzer.analyze_data(
            headers=["name", "age"],
            rows=[["Aman", "20"], ["Aman", "20"]],
        )

        dup_issues = [i for i in report.issues if i.issue_type == "duplicate_row"]
        self.assertEqual(len(dup_issues), 1)

        # In to_dict(), value must be a dictionary, not a str representation
        issue_dict = dup_issues[0].to_dict()
        self.assertIsInstance(issue_dict["value"], dict)
        self.assertEqual(issue_dict["value"], {"name": "Aman", "age": "20"})

        # In JSON export, round-tripping json.loads must yield a real dict
        json_str = report_to_json(report, display_name="test.csv")
        parsed = json.loads(json_str)
        parsed_issue_val = parsed["issues"][0]["value"]
        self.assertIsInstance(parsed_issue_val, dict)
        self.assertEqual(parsed_issue_val["name"], "Aman")
        self.assertEqual(parsed_issue_val["age"], "20")

    def test_cross_platform_path_sanitization_edge_cases(self):
        """sanitize_file_path must handle Windows backslashes cross-platform."""
        self.assertEqual(sanitize_file_path(r"D:\Data\Engineering\confidential.csv"), "confidential.csv")
        self.assertEqual(sanitize_file_path("/var/log/data/metrics.csv"), "metrics.csv")
        self.assertEqual(sanitize_file_path(r"C:\nested\path\file.csv", display_name="clean.csv"), "clean.csv")


if __name__ == "__main__":
    unittest.main()

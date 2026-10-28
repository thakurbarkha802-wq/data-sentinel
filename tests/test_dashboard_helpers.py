"""Unit tests for DataSentinel Dashboard Helpers and In-Memory Analysis
"""

import unittest
from core.dashboard_helpers import (
    build_download_filename,
    clear_all_rule_widget_states,
    clear_column_widget_state,
    extract_column_names,
    get_score_color,
    parse_rule_form_inputs,
)
from core.rules import ColumnRule
import app


class TestDashboardHelpers(unittest.TestCase):
    """Tests lightweight header extraction, form validation, widget isolation, and in-memory auditing."""

    def test_extract_column_names_valid(self):
        csv_bytes = b"id,name,department\n1,Alice,Engineering\n2,Bob,Product\n"
        cols = extract_column_names(csv_bytes)
        self.assertEqual(cols, ["id", "name", "department"])

    def test_extract_column_names_duplicate_and_empty(self):
        csv_bytes = b"id,name,email,name,\n1,Alice,alice@example.com,Alice2,extra\n"
        cols = extract_column_names(csv_bytes)
        self.assertEqual(cols, ["id", "name", "email", "name_2", "Unnamed_5"])

    def test_extract_column_names_empty_and_whitespace(self):
        self.assertEqual(extract_column_names(b""), [])
        self.assertEqual(extract_column_names(b"   \n\n\t\n"), [])

    def test_extract_column_names_utf8_bom(self):
        csv_bytes = "sku,price,qty\nSKU-1,10.5,100\n".encode("utf-8-sig")
        cols = extract_column_names(csv_bytes)
        self.assertEqual(cols, ["sku", "price", "qty"])

    def test_parse_rule_form_inputs_valid_int(self):
        rule, err = parse_rule_form_inputs(
            selected_col="age",
            rule_type="Integer (int)",
            has_min=True,
            min_val=18.0,
            has_max=True,
            max_val=65.0,
        )
        self.assertIsNone(err)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.column, "age")
        self.assertEqual(rule.data_type, "int")
        self.assertEqual(rule.min_value, 18.0)
        self.assertEqual(rule.max_value, 65.0)

    def test_parse_rule_form_inputs_unconstrained(self):
        rule, err = parse_rule_form_inputs(
            selected_col="notes",
            rule_type="None (Unconstrained)",
            has_min=False,
            min_val=None,
            has_max=False,
            max_val=None,
        )
        self.assertIsNone(err)
        self.assertIsNone(rule)

    def test_parse_rule_form_inputs_contradictory_range(self):
        rule, err = parse_rule_form_inputs(
            selected_col="score",
            rule_type="Integer (int)",
            has_min=True,
            min_val=100.0,
            has_max=True,
            max_val=50.0,
        )
        self.assertIsNone(rule)
        self.assertIsNotNone(err)
        self.assertIn("cannot exceed maximum", err.lower())

    def test_parse_rule_form_inputs_type_mapping(self):
        # Float
        r_float, _ = parse_rule_form_inputs("price", "Decimal (float)", False, None, False, None)
        self.assertEqual(r_float.data_type, "float")

        # String
        r_str, _ = parse_rule_form_inputs("city", "Text (str)", False, None, False, None)
        self.assertEqual(r_str.data_type, "str")

    def test_clear_column_widget_state(self):
        state = {
            "rule_type_age": "Integer (int)",
            "rule_has_min_age": True,
            "rule_min_val_age": 0.0,
            "rule_type_city": "Text (str)",
            "other_key": 123,
        }
        clear_column_widget_state(state, "age")
        self.assertNotIn("rule_type_age", state)
        self.assertNotIn("rule_has_min_age", state)
        self.assertNotIn("rule_min_val_age", state)
        # Other column and unrelated keys preserved
        self.assertEqual(state["rule_type_city"], "Text (str)")
        self.assertEqual(state["other_key"], 123)

    def test_clear_all_rule_widget_states(self):
        state = {
            "rule_type_age": "Integer (int)",
            "rule_type_city": "Text (str)",
            "rule_min_val_salary": 50000.0,
            "unrelated_session_var": "keep_me",
        }
        clear_all_rule_widget_states(state)
        self.assertNotIn("rule_type_age", state)
        self.assertNotIn("rule_type_city", state)
        self.assertNotIn("rule_min_val_salary", state)
        self.assertEqual(state["unrelated_session_var"], "keep_me")

    def test_build_download_filename(self):
        self.assertEqual(build_download_filename("customer data.csv"), "datasentinel_report_customer_data.json")
        self.assertEqual(build_download_filename(r"C:\Secret\sales.csv"), "datasentinel_report_sales.json")
        self.assertEqual(build_download_filename("/var/log/data/metrics.csv"), "datasentinel_report_metrics.json")

    def test_get_score_color(self):
        self.assertEqual(get_score_color(95.0), "#28a745")
        self.assertEqual(get_score_color(80.0), "#28a745")
        self.assertEqual(get_score_color(79.9), "#ffc107")
        self.assertEqual(get_score_color(60.0), "#ffc107")
        self.assertEqual(get_score_color(59.9), "#dc3545")
        self.assertEqual(get_score_color(0.0), "#dc3545")

    def test_run_audit_in_memory_direct(self):
        """Verifies run_audit analyzes CSV bytes in-memory and outputs expected report without disk writes."""
        csv_bytes = b"name,age,city\nAman,20,Delhi\nKabir,-5,Agra\n"
        rules = {"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=120)}
        report = app.run_audit(csv_bytes, "in_memory_test.csv", rules)

        self.assertIsNotNone(report)
        self.assertEqual(report.file_path, "in_memory_test.csv")
        self.assertEqual(report.total_rows, 2)
        self.assertEqual(report.total_columns, 3)
        self.assertEqual(report.invalid_values_count, 1)  # -5
        self.assertEqual(report.missing_values_count, 0)
        self.assertEqual(report.scores.completeness, 100.0)
        self.assertEqual(report.scores.validity, 50.0)


if __name__ == "__main__":
    unittest.main()

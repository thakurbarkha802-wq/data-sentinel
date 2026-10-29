"""Unit tests for DataSentinel Transparent Scoring System
"""

import unittest
from core.analyzer import DataSentinel
from core.rules import ColumnRule


class TestScoringSystem(unittest.TestCase):
    """Tests dimension scoring, formulas, edge cases, and zero-row safety."""

    def test_perfect_dataset_achieves_100_percent(self):
        headers = ["id", "name", "score"]
        rows = [
            ["1", "Alice", "95"],
            ["2", "Bob", "88"],
            ["3", "Charlie", "72"],
        ]
        analyzer = DataSentinel(
            rules={"score": ColumnRule(column="score", data_type="int", min_value=0, max_value=100)}
        )
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.scores.completeness, 100.0)
        self.assertEqual(report.scores.validity, 100.0)
        self.assertEqual(report.scores.uniqueness, 100.0)
        self.assertEqual(report.scores.overall, 100.0)

    def test_zero_row_empty_dataset_scores_zero(self):
        """Verifies that an empty dataset safely returns 0.0 without ZeroDivisionError."""
        headers = ["id", "name", "score"]
        rows = []
        analyzer = DataSentinel()
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.total_rows, 0)
        self.assertEqual(report.scores.completeness, 0.0)
        self.assertEqual(report.scores.validity, 0.0)
        self.assertEqual(report.scores.uniqueness, 0.0)
        self.assertEqual(report.scores.overall, 0.0)

    def test_completeness_calculation(self):
        # 4 rows, 2 columns = 8 cells.
        # 2 missing cells (1 empty string, 1 whitespace-only).
        # Completeness should be (6 / 8) * 100 = 75.0%
        headers = ["col1", "col2"]
        rows = [
            ["a", "b"],
            ["", "d"],
            ["e", "   "],
            ["g", "h"],
        ]
        analyzer = DataSentinel()
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.missing_values_count, 2)
        self.assertEqual(report.scores.completeness, 75.0)

    def test_uniqueness_calculation_and_duplicate_counting(self):
        # 5 rows. Row 1: (A, 1), Row 2: (B, 2), Row 3: (A, 1) [dup], Row 4: (A, 1) [dup], Row 5: (C, 3)
        # Total duplicates = 2.
        # Uniqueness should be ((5 - 2) / 5) * 100 = 60.0%
        # Line numbers: header is 1, rows are 2, 3, 4, 5, 6.
        # Duplicates are at lines 4 and 5 (matching line 2).
        headers = ["name", "id"]
        rows = [
            ["A", "1"],
            ["B", "2"],
            ["A", "1"],
            ["A", "1"],
            ["C", "3"],
        ]
        analyzer = DataSentinel()
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.duplicate_rows_count, 2)
        self.assertEqual(report.duplicate_row_numbers, [4, 5])
        self.assertEqual(report.scores.uniqueness, 60.0)

    def test_validity_calculation_with_unconfigured_columns(self):
        # 4 rows, 2 columns: 'id' (unconfigured) and 'age' (rule: int [0, 100]).
        # Evaluated cells = 4 cells in 'age'.
        # 1 invalid cell in 'age' (age = -10).
        # Validity should be ((4 - 1) / 4) * 100 = 75.0%.
        # Unconfigured 'id' column does not artificially dilute validity to (7/8 = 87.5%).
        headers = ["id", "age"]
        rows = [
            ["1", "20"],
            ["2", "30"],
            ["3", "-10"],  # invalid
            ["4", "40"],
        ]
        analyzer = DataSentinel(
            rules={"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=100)}
        )
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.invalid_values_count, 1)
        self.assertEqual(report.scores.validity, 75.0)

    def test_plain_string_rule_does_not_inflate_validity_score(self):
        """A plain data_type='str' rule has no enforceable constraints and must not inflate validity."""
        headers = ["id", "age", "city"]
        rows = [
            ["1", "20", "Delhi"],
            ["2", "30", "Mumbai"],
            ["3", "-10", "Kolkata"],  # invalid age
            ["4", "40", "Chennai"],
        ]
        # Without string rule, validity is 75.0% (3/4 valid in 'age').
        # Adding a plain string rule on 'city' must NOT dilute/inflate validity to (7/8 = 87.5%).
        analyzer = DataSentinel(
            rules={
                "age": ColumnRule(column="age", data_type="int", min_value=0, max_value=100),
                "city": ColumnRule(column="city", data_type="str"),
            }
        )
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.invalid_values_count, 1)
        self.assertEqual(report.scores.validity, 75.0)

    def test_validity_when_no_rules_configured(self):
        # If no rules are configured at all, validity should default to 100.0%
        headers = ["name", "city"]
        rows = [
            ["Aman", "Delhi"],
            ["Riya", "Mathura"],
        ]
        analyzer = DataSentinel()
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.scores.validity, 100.0)

    def test_validity_when_only_unconstrained_rules_configured(self):
        # If only unconstrained rules (like data_type='str') are configured, validity should default to 100.0%
        headers = ["name", "city"]
        rows = [
            ["Aman", "Delhi"],
            ["Riya", "Mathura"],
        ]
        analyzer = DataSentinel(rules={"city": ColumnRule(column="city", data_type="str")})
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.scores.validity, 100.0)

    def test_unconstrained_custom_rule_cannot_create_invalid_findings_or_distort_validity(self):
        """Custom rules with is_constrained=False are excluded from validity evaluation."""
        class MockUnconstrainedRejectingRule:
            is_constrained = False
            def validate(self, val):
                return False, "Rejected by unconstrained rule"
            def describe(self):
                return "Mock Unconstrained Rule"

        headers = ["id", "age", "notes"]
        rows = [
            ["1", "20", "val1"],
            ["2", "30", "val2"],
            ["3", "-10", "val3"],  # invalid age (1 of 4 invalid)
            ["4", "40", "val4"],
        ]
        # 'notes' has an unconstrained rule that would reject values,
        # but because is_constrained=False, 'notes' is excluded from validity evaluation.
        # It must not generate invalid findings or distort validity from 75.0%.
        analyzer = DataSentinel(
            rules={
                "age": ColumnRule(column="age", data_type="int", min_value=0, max_value=100),
                "notes": MockUnconstrainedRejectingRule(),
            }
        )
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.invalid_values_count, 1)
        self.assertEqual(report.scores.validity, 75.0)
        invalid_issues = [i for i in report.issues if i.issue_type == "invalid_value"]
        self.assertEqual(len(invalid_issues), 1)
        self.assertEqual(invalid_issues[0].column, "age")

    def test_legacy_custom_rule_without_is_constrained_defaults_to_constrained(self):
        """Custom or legacy rule objects that omit is_constrained default safely to constrained."""
        class LegacyCustomRule:
            def validate(self, val):
                if val == "bad":
                    return False, "Legacy rejection"
                return True, None
            def describe(self):
                return "Legacy Rule"

        headers = ["status"]
        rows = [["good"], ["bad"]]
        analyzer = DataSentinel(rules={"status": LegacyCustomRule()})
        report = analyzer.analyze_data(headers, rows)

        self.assertEqual(report.invalid_values_count, 1)
        self.assertEqual(report.scores.validity, 50.0)

    def test_weighted_overall_score_formula(self):
        # Verify: Overall = (0.35 * completeness) + (0.35 * validity) + (0.30 * uniqueness)
        headers = ["age"]
        # 4 rows:
        # Row 1: "20" (valid)
        # Row 2: "20" (duplicate of row 1, valid)
        # Row 3: ""   (missing)
        # Row 4: "-5" (invalid)
        # Total cells = 4. Missing = 1 -> Completeness = (3/4)*100 = 75.0%
        # Evaluated cells = 3 (non-blank 'age'). Invalid = 1 -> Validity = (2/3)*100 = 66.67%
        # Rows = 4. Duplicates = 1 -> Uniqueness = (3/4)*100 = 75.0%
        # Expected Overall = 0.35*75.0 + 0.35*66.67 + 0.30*75.0 = 26.25 + 23.3345 + 22.50 = 72.08
        analyzer = DataSentinel(
            rules={"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=120)}
        )
        report = analyzer.analyze_data(headers, [["20"], ["20"], [""], ["-5"]])

        self.assertEqual(report.scores.completeness, 75.0)
        self.assertEqual(report.scores.validity, 66.67)
        self.assertEqual(report.scores.uniqueness, 75.0)
        self.assertEqual(report.scores.overall, 72.08)

    def test_duplicate_headers_completeness_bounded(self):
        """Verifies duplicate headers do not corrupt column summaries or produce negative scores."""
        headers = ["name", "age", "name"]
        rows = [
            ["", "20", ""],
            ["", "25", ""],
        ]
        analyzer = DataSentinel()
        report = analyzer.analyze_data(headers, rows)

        # Both columns should exist with distinct names
        self.assertIn("name", report.column_summaries)
        self.assertIn("name_2", report.column_summaries)
        
        # Missing counts and completeness scores must be non-negative and properly isolated
        for col_name, summary in report.column_summaries.items():
            self.assertGreaterEqual(summary.completeness_score, 0.0)
            self.assertLessEqual(summary.completeness_score, 100.0)
            self.assertLessEqual(summary.missing_count, summary.total_cells)

        # Overall completeness score must be valid
        self.assertGreaterEqual(report.scores.completeness, 0.0)
        self.assertLessEqual(report.scores.completeness, 100.0)

    def test_dimension_scores_clamped_strictly_between_0_and_100(self):
        """All dimension scores and overall score must remain strictly within [0.0, 100.0]."""
        # Empty dataset
        analyzer = DataSentinel()
        empty_report = analyzer.analyze_data([], [])
        for score_val in [
            empty_report.scores.completeness,
            empty_report.scores.validity,
            empty_report.scores.uniqueness,
            empty_report.scores.overall,
        ]:
            self.assertEqual(score_val, 0.0)


if __name__ == "__main__":
    unittest.main()

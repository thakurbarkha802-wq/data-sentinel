"""Unit tests for DataSentinel Column Validation Rules
"""

import unittest
from core.rules import ColumnRule


class TestColumnRules(unittest.TestCase):
    """Tests data type validation, numeric ranges, and rule edge cases."""

    def test_integer_valid_range(self):
        rule = ColumnRule(column="age", data_type="int", min_value=0, max_value=120)
        is_valid, reason = rule.validate("25")
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

        # Boundary checks
        self.assertTrue(rule.validate("0")[0])
        self.assertTrue(rule.validate("120")[0])

    def test_integer_out_of_range(self):
        rule = ColumnRule(column="age", data_type="int", min_value=0, max_value=120)
        
        # Below min
        is_valid, reason = rule.validate("-5")
        self.assertFalse(is_valid)
        self.assertIn("below minimum", reason.lower())

        # Above max
        is_valid, reason = rule.validate("150")
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum", reason.lower())

    def test_integer_non_numeric_and_decimal(self):
        rule = ColumnRule(column="age", data_type="int", min_value=0, max_value=120)

        # Non-numeric string
        is_valid, reason = rule.validate("twenty")
        self.assertFalse(is_valid)
        self.assertIn("non-numeric", reason.lower())

        # Decimal string should be rejected for integer rule
        is_valid, reason = rule.validate("25.5")
        self.assertFalse(is_valid)
        self.assertIn("decimal", reason.lower())

    def test_float_valid_and_out_of_range(self):
        rule = ColumnRule(column="price", data_type="float", min_value=0.01, max_value=999.99)
        self.assertTrue(rule.validate("19.99")[0])
        self.assertTrue(rule.validate("100")[0])

        # Below min
        is_valid, reason = rule.validate("0.00")
        self.assertFalse(is_valid)
        self.assertIn("below minimum", reason.lower())

        # Above max
        is_valid, reason = rule.validate("1500.50")
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum", reason.lower())

    def test_blank_and_none_values_skipped(self):
        """Blank or None values return is_valid=True to avoid double-penalizing completeness."""
        rule = ColumnRule(column="score", data_type="int", min_value=0, max_value=100)
        self.assertTrue(rule.validate("")[0])
        self.assertTrue(rule.validate("   ")[0])
        self.assertTrue(rule.validate(None)[0])

    def test_rule_describe(self):
        rule = ColumnRule(column="age", data_type="int", min_value=0, max_value=120)
        desc = rule.describe()
        self.assertIn("int", desc)
        self.assertIn("[0, 120]", desc)

    def test_untyped_rule_enforces_numeric_min_max(self):
        """Rules with omitted data_type must enforce numeric min/max bounds."""
        rule = ColumnRule(column="score", min_value=10.0, max_value=50.0)
        
        # Valid values
        self.assertTrue(rule.validate("25")[0])
        self.assertTrue(rule.validate("10.0")[0])
        self.assertTrue(rule.validate("50")[0])

        # Out of bounds
        is_valid, reason = rule.validate("5")
        self.assertFalse(is_valid)
        self.assertIn("below minimum", reason.lower())

        is_valid, reason = rule.validate("75")
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum", reason.lower())

        # Non-numeric string
        is_valid, reason = rule.validate("not_a_number")
        self.assertFalse(is_valid)
        self.assertIn("numeric", reason.lower())

    def test_float_rule_rejects_nan_and_infinity(self):
        """Float validation must reject NaN, positive infinity, and negative infinity."""
        rule = ColumnRule(column="price", data_type="float", min_value=0.0, max_value=100.0)
        for bad_val in ["nan", "NaN", "NAN", "inf", "-inf", "+inf"]:
            is_valid, reason = rule.validate(bad_val)
            self.assertFalse(is_valid, f"Expected {bad_val} to be rejected")
            self.assertIn("non-finite", reason.lower())

    def test_contradictory_range_raises_value_error(self):
        """Instantiating ColumnRule with min_value > max_value or NaN must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="age", min_value=100, max_value=50)
        self.assertIn("contradictory range", str(ctx.exception).lower())

        with self.assertRaises(ValueError):
            ColumnRule(column="age", min_value=float("nan"), max_value=50)

    def test_string_rule_with_numeric_range_raises_value_error(self):
        """Configuring numeric range on data_type='str' must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="name", data_type="str", min_value=10)
        self.assertIn("cannot be configured with data_type='str'", str(ctx.exception).lower())

    def test_unsupported_data_type_raises_value_error(self):
        """Configuring unsupported data_type must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="flag", data_type="boolean")
        self.assertIn("unsupported data_type", str(ctx.exception).lower())

    def test_rule_is_constrained(self):
        """Verifies is_constrained accurately distinguishes enforceable rules from unconstrained ones."""
        # Enforceable rules
        self.assertTrue(ColumnRule(column="age", data_type="int").is_constrained)
        self.assertTrue(ColumnRule(column="price", data_type="float").is_constrained)
        self.assertTrue(ColumnRule(column="score", min_value=0.0).is_constrained)
        self.assertTrue(ColumnRule(column="score", max_value=100.0).is_constrained)

        # Unconstrained rules
        self.assertFalse(ColumnRule(column="name", data_type="str").is_constrained)
        self.assertFalse(ColumnRule(column="notes").is_constrained)


if __name__ == "__main__":
    unittest.main()

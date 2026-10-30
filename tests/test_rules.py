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

    def test_large_integer_preserves_precision_and_enforces_bounds(self):
        """Integers exceeding float representation (>308 digits) must not raise OverflowError."""
        # 400-digit integer exceeding max_value=100
        rule_bounded = ColumnRule(column="age", data_type="int", min_value=0, max_value=100)
        large_val = "1" * 400
        is_valid, reason = rule_bounded.validate(large_val)
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum allowed", reason.lower())

        # Negative 400-digit integer below min_value=0
        neg_large_val = "-" + ("1" * 400)
        is_valid, reason = rule_bounded.validate(neg_large_val)
        self.assertFalse(is_valid)
        self.assertIn("below minimum allowed", reason.lower())

        # Unbounded integer rule accepts arbitrary precision integers without error
        rule_unbounded = ColumnRule(column="big_id", data_type="int")
        is_valid, reason = rule_unbounded.validate(large_val)
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

        # Configured bounds with arbitrary-precision integers
        rule_large_bound = ColumnRule(column="big_bound", data_type="int", max_value=int("9" * 400))
        self.assertTrue(rule_large_bound.validate("1" * 400)[0])
        self.assertFalse(rule_large_bound.validate("1" + ("0" * 401))[0])

    def test_unbounded_float_rule_rejects_nan_and_infinity(self):
        """Unbounded float rule (no min/max) must still reject NaN and positive/negative infinity."""
        rule = ColumnRule(column="measurement", data_type="float")
        for bad_val in ["nan", "NaN", "NAN", "inf", "-inf", "+inf", "Infinity", "-Infinity"]:
            is_valid, reason = rule.validate(bad_val)
            self.assertFalse(is_valid, f"Expected {bad_val} to be rejected")
            self.assertIn("non-finite", reason.lower())

    def test_untyped_range_rule_rejects_nan_and_infinity(self):
        """Untyped range rule must reject NaN and positive/negative infinity."""
        rule = ColumnRule(column="score", min_value=0.0, max_value=100.0)
        for bad_val in ["nan", "NaN", "NAN", "inf", "-inf", "+inf", "Infinity", "-Infinity"]:
            is_valid, reason = rule.validate(bad_val)
            self.assertFalse(is_valid, f"Expected {bad_val} to be rejected")
            self.assertIn("non-finite", reason.lower())

    def test_infinite_constructor_bounds_raise_value_error(self):
        """Configuring positive or negative infinity as min_value or max_value must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", min_value=float("inf"))
        self.assertIn("must be a finite number", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", min_value=float("-inf"))
        self.assertIn("must be a finite number", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", max_value=float("inf"))
        self.assertIn("must be a finite number", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", max_value=float("-inf"))
        self.assertIn("must be a finite number", str(ctx.exception).lower())

    def test_scientific_notation_and_single_sided_bounds(self):
        """Verifies scientific notation parsing and single-sided min/max range constraints."""
        # Float scientific notation
        rule_sci = ColumnRule(column="rate", data_type="float", min_value=0.001, max_value=100000.0)
        self.assertTrue(rule_sci.validate("1e-3")[0])
        self.assertTrue(rule_sci.validate("1e5")[0])
        self.assertFalse(rule_sci.validate("1e-4")[0])  # Below min
        self.assertFalse(rule_sci.validate("1e6")[0])   # Above max

        # Single-sided minimum bound on int
        rule_min = ColumnRule(column="count", data_type="int", min_value=10)
        self.assertTrue(rule_min.validate("10")[0])
        self.assertTrue(rule_min.validate("100")[0])
        self.assertFalse(rule_min.validate("5")[0])

        # Single-sided maximum bound on float
        rule_max = ColumnRule(column="temp", max_value=40.0)
        self.assertTrue(rule_max.validate("40.0")[0])
        self.assertTrue(rule_max.validate("25.5")[0])
        self.assertFalse(rule_max.validate("45.0")[0])

    def test_invalid_bound_types_raise_type_error(self):
        """Passing non-int/float types (e.g. str, list, dict, bool) as min_value or max_value raises TypeError."""
        bad_bounds = ["10", "abc", [1, 2], {"min": 0}, True, False, complex(1, 2)]

        for bad_val in bad_bounds:
            expected_type = type(bad_val).__name__

            # Test invalid min_value (single-sided)
            with self.assertRaises(TypeError) as ctx:
                ColumnRule(column="test_col", min_value=bad_val)
            err_msg = str(ctx.exception)
            self.assertIn("test_col", err_msg)
            self.assertIn("min_value", err_msg)
            self.assertIn(expected_type, err_msg)

            # Test invalid max_value (single-sided)
            with self.assertRaises(TypeError) as ctx:
                ColumnRule(column="test_col", max_value=bad_val)
            err_msg = str(ctx.exception)
            self.assertIn("test_col", err_msg)
            self.assertIn("max_value", err_msg)
            self.assertIn(expected_type, err_msg)

            # Test invalid min_value with valid max_value
            with self.assertRaises(TypeError) as ctx:
                ColumnRule(column="test_col", min_value=bad_val, max_value=100)
            self.assertIn("min_value", str(ctx.exception))

            # Test invalid max_value with valid min_value
            with self.assertRaises(TypeError) as ctx:
                ColumnRule(column="test_col", min_value=0, max_value=bad_val)
            self.assertIn("max_value", str(ctx.exception))

    def test_single_sided_nan_constructor_bounds_raise_value_error(self):
        """Single-sided NaN bounds for min_value or max_value must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", min_value=float("nan"))
        self.assertIn("must be a finite number", str(ctx.exception).lower())
        self.assertIn("min_value", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", max_value=float("nan"))
        self.assertIn("must be a finite number", str(ctx.exception).lower())
        self.assertIn("max_value", str(ctx.exception))

    def test_mixed_integer_and_float_bounds(self):
        """Mixed int and float bounds enforce constraints and validate contradictory ranges correctly."""
        # int min, float max on integer rule
        rule_int_float = ColumnRule(column="count", data_type="int", min_value=0, max_value=10.5)
        self.assertTrue(rule_int_float.validate("0")[0])
        self.assertTrue(rule_int_float.validate("10")[0])
        self.assertFalse(rule_int_float.validate("11")[0])
        self.assertFalse(rule_int_float.validate("-1")[0])

        # float min, int max on integer rule
        rule_float_int = ColumnRule(column="count", data_type="int", min_value=0.5, max_value=10)
        self.assertFalse(rule_float_int.validate("0")[0])
        self.assertTrue(rule_float_int.validate("1")[0])
        self.assertTrue(rule_float_int.validate("10")[0])
        self.assertFalse(rule_float_int.validate("11")[0])

        # Mixed bounds on float rule
        rule_float_mixed = ColumnRule(column="score", data_type="float", min_value=0, max_value=10.5)
        self.assertTrue(rule_float_mixed.validate("0.0")[0])
        self.assertTrue(rule_float_mixed.validate("10.5")[0])
        self.assertFalse(rule_float_mixed.validate("10.51")[0])
        self.assertFalse(rule_float_mixed.validate("-0.01")[0])

        # Contradictory mixed bounds raise ValueError
        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", min_value=10.5, max_value=10)
        self.assertIn("contradictory range", str(ctx.exception).lower())

        with self.assertRaises(ValueError) as ctx:
            ColumnRule(column="col", min_value=10, max_value=9.9)
        self.assertIn("contradictory range", str(ctx.exception).lower())

    def test_large_integer_against_float_bounds(self):
        """Large integer inputs (>308 digits) must be cleanly evaluated against float bounds."""
        rule = ColumnRule(column="age", data_type="int", min_value=0.0, max_value=100.0)

        # Large positive int (>100.0)
        large_pos = "1" * 400
        is_valid, reason = rule.validate(large_pos)
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum allowed", reason.lower())

        # Large negative int (<0.0)
        large_neg = "-" + ("1" * 400)
        is_valid, reason = rule.validate(large_neg)
        self.assertFalse(is_valid)
        self.assertIn("below minimum allowed", reason.lower())

        # Valid in-range value
        is_valid, reason = rule.validate("50")
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

        # Single-sided float bounds
        rule_single_max = ColumnRule(column="age", data_type="int", max_value=100.0)
        self.assertFalse(rule_single_max.validate(large_pos)[0])
        self.assertTrue(rule_single_max.validate("50")[0])

        rule_single_min = ColumnRule(column="age", data_type="int", min_value=0.0)
        self.assertFalse(rule_single_min.validate(large_neg)[0])
        self.assertTrue(rule_single_min.validate("50")[0])


if __name__ == "__main__":
    unittest.main()

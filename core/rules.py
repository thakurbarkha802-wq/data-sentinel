"""DataSentinel Column Validation Rules

Allows configurable rules per column (e.g. data type checks, numeric ranges)
without hardcoding schema details into the engine.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple, Any


@dataclass
class ColumnRule:
    """Validation rule for a specific CSV column."""
    column: str
    data_type: Optional[str] = None  # "int", "float", "str"
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def __post_init__(self) -> None:
        """Validates configuration parameters upon rule creation."""
        # 1. Validate data_type
        if self.data_type is not None and self.data_type not in ("int", "float", "str"):
            raise ValueError(
                f"Column '{self.column}': unsupported data_type '{self.data_type}'. "
                f"Must be one of: 'int', 'float', 'str', or None."
            )

        # 2. Reject numeric range constraints on string columns
        if self.data_type == "str" and (self.min_value is not None or self.max_value is not None):
            raise ValueError(
                f"Column '{self.column}': numeric range constraints (min/max) "
                f"cannot be configured with data_type='str'."
            )

        # 3. Reject NaN or infinite values in range bounds
        if self.min_value is not None:
            if math.isnan(self.min_value) or math.isinf(self.min_value):
                raise ValueError(
                    f"Column '{self.column}': min_value must be a finite number, found {self.min_value}."
                )
        if self.max_value is not None:
            if math.isnan(self.max_value) or math.isinf(self.max_value):
                raise ValueError(
                    f"Column '{self.column}': max_value must be a finite number, found {self.max_value}."
                )

        # 4. Reject contradictory ranges (min_value > max_value)
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise ValueError(
                    f"Column '{self.column}': contradictory range configuration: "
                    f"min_value ({self.min_value}) cannot exceed max_value ({self.max_value})."
                )

    @property
    def is_constrained(self) -> bool:
        """Indicates whether this rule defines any enforceable constraint that can fail validation."""
        if self.data_type in ("int", "float"):
            return True
        if self.min_value is not None or self.max_value is not None:
            return True
        return False

    def describe(self) -> str:
        parts = []
        if self.data_type:
            parts.append(f"Type: {self.data_type}")
        if self.min_value is not None and self.max_value is not None:
            parts.append(f"Range: [{self.min_value}, {self.max_value}]")
        elif self.min_value is not None:
            parts.append(f"Min: {self.min_value}")
        elif self.max_value is not None:
            parts.append(f"Max: {self.max_value}")
        return ", ".join(parts) if parts else "No constraints"

    def validate(self, raw_value: Any) -> Tuple[bool, Optional[str]]:
        """Validates a non-blank string value against configured constraints.
        
        Returns:
            (is_valid, failure_reason)
        """
        if raw_value is None:
            return True, None

        val_str = str(raw_value).strip()
        if val_str == "":
            return True, None  # Empty values are handled by the completeness dimension

        numeric_val: Optional[float] = None

        # 1. Type validation
        if self.data_type == "int":
            try:
                # Ensure it's purely integer format, not a floating point string like "20.5"
                if "." in val_str:
                    return False, f"Expected integer, found decimal value '{val_str}'"
                int_val = int(val_str)
                numeric_val = float(int_val)
            except ValueError:
                return False, f"Expected integer, found non-numeric value '{val_str}'"

        elif self.data_type == "float":
            try:
                parsed = float(val_str)
                if math.isnan(parsed) or math.isinf(parsed):
                    return False, f"Expected finite float, found non-finite value '{val_str}'"
                numeric_val = parsed
            except ValueError:
                return False, f"Expected float, found non-numeric value '{val_str}'"

        elif self.data_type is None and (self.min_value is not None or self.max_value is not None):
            # Implicit numeric type when min_value or max_value is configured without explicit data_type
            try:
                parsed = float(val_str)
                if math.isnan(parsed) or math.isinf(parsed):
                    return False, f"Expected finite numeric value, found non-finite value '{val_str}'"
                numeric_val = parsed
            except ValueError:
                return False, f"Expected numeric value for range validation, found non-numeric value '{val_str}'"

        # 2. Numeric range validation
        if numeric_val is not None:
            if self.min_value is not None and numeric_val < self.min_value:
                return False, f"Value {val_str} is below minimum allowed ({self.min_value})"
            if self.max_value is not None and numeric_val > self.max_value:
                return False, f"Value {val_str} exceeds maximum allowed ({self.max_value})"

        return True, None

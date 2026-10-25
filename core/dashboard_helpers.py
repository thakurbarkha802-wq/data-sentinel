"""DataSentinel Dashboard Helpers

Pure, testable helper functions for Streamlit UI state management,
lightweight header extraction, and input validation.
"""

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional, Tuple

from .loader import deduplicate_headers
from .rules import ColumnRule


def extract_column_names(file_bytes: bytes) -> List[str]:
    """Extracts deduplicated column names from CSV bytes without running a full audit.
    
    Args:
        file_bytes: Raw bytes of the CSV dataset.
        
    Returns:
        List of unique column names, or empty list if file has no valid headers.
    """
    if not file_bytes:
        return []

    try:
        text = file_bytes.decode("utf-8-sig", errors="replace")
        stream = io.StringIO(text)
        reader = csv.reader(stream)
        first_line = next(reader)
        raw_headers = [h.strip().lstrip("\ufeff") for h in first_line]
        if not raw_headers or all(h == "" for h in raw_headers):
            return []
        headers, _ = deduplicate_headers(raw_headers)
        return headers
    except (StopIteration, Exception):
        return []


def parse_rule_form_inputs(
    selected_col: str,
    rule_type: str,
    has_min: bool,
    min_val: Optional[float],
    has_max: bool,
    max_val: Optional[float],
) -> Tuple[Optional[ColumnRule], Optional[str]]:
    """Validates and parses UI rule form inputs into a ColumnRule.
    
    Args:
        selected_col: Target column name.
        rule_type: UI selectbox selection (e.g. 'Integer (int)', 'Decimal (float)').
        has_min: Whether minimum checkbox is checked.
        min_val: Specified minimum value if has_min is True.
        has_max: Whether maximum checkbox is checked.
        max_val: Specified maximum value if has_max is True.
        
    Returns:
        (ColumnRule, None) on success.
        (None, None) if rule is unconstrained (should be removed).
        (None, error_message) if input is contradictory or invalid.
    """
    parsed_type: Optional[str] = None
    if "Integer" in rule_type:
        parsed_type = "int"
    elif "Decimal" in rule_type:
        parsed_type = "float"
    elif "Text" in rule_type:
        parsed_type = "str"

    effective_min = min_val if has_min else None
    effective_max = max_val if has_max else None

    # If completely unconstrained, signal rule removal
    if parsed_type is None and effective_min is None and effective_max is None:
        return None, None

    # Validate min <= max if both are configured
    if effective_min is not None and effective_max is not None and effective_min > effective_max:
        return (
            None,
            f"Cannot save rule for '{selected_col}': Minimum value ({effective_min}) "
            f"cannot exceed maximum value ({effective_max}).",
        )

    try:
        rule = ColumnRule(
            column=selected_col,
            data_type=parsed_type,
            min_value=effective_min,
            max_value=effective_max,
        )
        return rule, None
    except ValueError as e:
        return None, str(e)


def build_download_filename(display_name: str) -> str:
    """Builds a sanitized report download filename based on the dataset name."""
    clean_base = Path(display_name).stem if display_name else "dataset"
    clean_base = clean_base.replace(" ", "_")
    return f"datasentinel_report_{clean_base}.json"


def get_score_color(score: float, threshold: float = 80.0) -> str:
    """Returns a status hex color code based on quality score."""
    if score >= threshold:
        return "#28a745"  # Green
    elif score >= 60.0:
        return "#ffc107"  # Amber
    return "#dc3545"      # Red


def clear_column_widget_state(session_state: MutableMapping[str, Any], col: str) -> None:
    """Clears cached widget keys for a specific column to reset widget state."""
    prefixes = ["rule_type_", "rule_has_min_", "rule_min_val_", "rule_has_max_", "rule_max_val_"]
    for prefix in prefixes:
        session_state.pop(f"{prefix}{col}", None)


def clear_all_rule_widget_states(session_state: MutableMapping[str, Any]) -> None:
    """Clears all column-scoped rule widget keys from session state."""
    prefixes = ("rule_type_", "rule_has_min_", "rule_min_val_", "rule_has_max_", "rule_max_val_")
    keys_to_clear = [k for k in list(session_state.keys()) if any(k.startswith(p) for p in prefixes)]
    for k in keys_to_clear:
        session_state.pop(k, None)

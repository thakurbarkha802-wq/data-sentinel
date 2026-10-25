"""DataSentinel Report Export and Serialization

Provides safe, sanitized serialization of QualityReport instances for downloads,
APIs, and dashboard exports without exposing local system paths or secrets.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .models import QualityReport


def sanitize_file_path(file_path: str, display_name: Optional[str] = None) -> str:
    """Sanitizes file path to prevent leaking local disk structures.
    
    If display_name is provided, uses it directly.
    Otherwise, extracts only the file's basename (e.g. 'dataset.csv'),
    reliably handling both POSIX ('/') and Windows ('\\') path separators.
    """
    if display_name:
        target = display_name
    elif file_path.startswith("<") and file_path.endswith(">"):
        return file_path
    else:
        target = file_path

    # Normalize Windows backslashes so basename extraction works across platforms
    normalized = target.replace("\\", "/").rstrip("/")
    basename = normalized.split("/")[-1]
    return basename or target


def serialize_report(
    report: QualityReport,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Safely converts a QualityReport to a sanitized dictionary for export.
    
    Args:
        report: The QualityReport instance to serialize.
        display_name: Optional user-facing filename to replace any absolute path.
        
    Returns:
        JSON-serializable dictionary with sanitized file path and structured metrics.
    """
    data = report.to_dict()
    data["file_path"] = sanitize_file_path(report.file_path, display_name)
    return data


def report_to_json(
    report: QualityReport,
    display_name: Optional[str] = None,
    indent: int = 2,
) -> str:
    """Converts a QualityReport to a pretty-printed, sanitized JSON string.
    
    Args:
        report: The QualityReport instance to serialize.
        display_name: Optional user-facing filename to replace any absolute path.
        indent: Indentation level for pretty-printing.
        
    Returns:
        Safe JSON string ready for file download or API response.
    """
    serialized = serialize_report(report, display_name=display_name)
    return json.dumps(serialized, indent=indent, ensure_ascii=False)

"""DataSentinel Interactive Dashboard

Streamlit web application for real-time data quality auditing, transparent scoring,
interactive rule configuration, and findings exploration.
"""

import io
import json
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

from core.analyzer import DataSentinel
from core.dashboard_helpers import (
    build_download_filename,
    clear_all_rule_widget_states,
    clear_column_widget_state,
    extract_column_names,
    get_score_color,
    parse_rule_form_inputs,
)
from core.export import report_to_json, serialize_report
from core.loader import DataSentinelError
from core.models import QualityIssue, QualityReport
from core.rules import ColumnRule

# Page configuration
st.set_page_config(
    page_title="DataSentinel — Data Quality & Observability",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom styling for high-contrast, clean visual presentation
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .score-badge {
        font-size: 2.2rem;
        font-weight: 700;
    }
    .score-label {
        font-size: 0.9rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_default_demo_path() -> Path:
    """Returns the path to the included sample.csv demo dataset."""
    demo_path = Path(__file__).resolve().parent / "sample.csv"
    return demo_path


def get_default_rules_for_dataset(column_names: List[str]) -> Dict[str, ColumnRule]:
    """Provides sensible default rules if known columns (like 'age') are detected."""
    rules: Dict[str, ColumnRule] = {}
    if "age" in column_names:
        rules["age"] = ColumnRule(
            column="age",
            data_type="int",
            min_value=0,
            max_value=120,
        )
    return rules


def run_audit(
    file_bytes: bytes,
    display_name: str,
    rules: Dict[str, ColumnRule],
) -> Optional[QualityReport]:
    """Safely executes DataSentinel analysis in memory without disk persistence.
    
    Ensures local file paths are not leaked and resources are cleaned up immediately.
    """
    try:
        csv_text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        st.error(
            f"**File Encoding Error:** Unable to decode '{display_name}' as UTF-8: {e}. "
            "Please ensure the file is saved with UTF-8 encoding."
        )
        return None
    except Exception as e:
        st.error(f"**File Read Error:** {e}")
        return None

    try:
        analyzer = DataSentinel(rules=rules)
        report = analyzer.analyze_stream(io.StringIO(csv_text), file_path=display_name)
        return report
    except DataSentinelError as e:
        st.error(f"**Data Validation Error:** {e}")
        return None
    except Exception as e:
        st.error(f"**Unexpected Processing Error:** {e}")
        return None


def render_sidebar(current_cols: List[str]) -> Dict[str, ColumnRule]:
    """Renders the sidebar navigation, rule editor, and dataset info with stable state isolation."""
    st.sidebar.title("🛡️ DataSentinel")
    st.sidebar.caption("Data Quality & Observability Platform")
    st.sidebar.divider()

    st.sidebar.subheader("⚙️ Validation Rules")
    st.sidebar.markdown(
        "Configure custom constraints for columns. Unconfigured columns remain unconstrained."
    )

    if "rules" not in st.session_state:
        st.session_state["rules"] = {}

    current_rules: Dict[str, ColumnRule] = st.session_state["rules"]

    if current_cols:
        with st.sidebar.expander("Add or Edit Column Rule", expanded=False):
            selected_col = st.selectbox("Target Column", options=current_cols, key="rule_col_select")
            
            existing_rule = current_rules.get(selected_col)
            default_type_idx = 0
            if existing_rule and existing_rule.data_type == "int":
                default_type_idx = 1
            elif existing_rule and existing_rule.data_type == "float":
                default_type_idx = 2
            elif existing_rule and existing_rule.data_type == "str":
                default_type_idx = 3

            # Column-scoped widget keys prevent state bleed across columns
            type_key = f"rule_type_{selected_col}"
            has_min_key = f"rule_has_min_{selected_col}"
            min_val_key = f"rule_min_val_{selected_col}"
            has_max_key = f"rule_has_max_{selected_col}"
            max_val_key = f"rule_max_val_{selected_col}"

            rule_type = st.selectbox(
                "Data Type Check",
                options=["None (Unconstrained)", "Integer (int)", "Decimal (float)", "Text (str)"],
                index=default_type_idx,
                key=type_key,
            )

            min_val = None
            max_val = None

            if "Integer" in rule_type or "Decimal" in rule_type:
                col_min, col_max = st.columns(2)
                with col_min:
                    default_has_min = existing_rule.min_value is not None if existing_rule else False
                    has_min = st.checkbox("Set Min", value=default_has_min, key=has_min_key)
                    if has_min:
                        init_min = float(existing_rule.min_value) if (existing_rule and existing_rule.min_value is not None) else 0.0
                        min_val = st.number_input("Minimum", value=init_min, step=1.0, key=min_val_key)
                with col_max:
                    default_has_max = existing_rule.max_value is not None if existing_rule else False
                    has_max = st.checkbox("Set Max", value=default_has_max, key=has_max_key)
                    if has_max:
                        init_max = float(existing_rule.max_value) if (existing_rule and existing_rule.max_value is not None) else 100.0
                        max_val = st.number_input("Maximum", value=init_max, step=1.0, key=max_val_key)

            c_save, c_remove = st.columns(2)
            with c_save:
                if st.button("Save Rule", use_container_width=True, type="primary"):
                    rule, err = parse_rule_form_inputs(
                        selected_col=selected_col,
                        rule_type=rule_type,
                        has_min=has_min if ("Integer" in rule_type or "Decimal" in rule_type) else False,
                        min_val=min_val,
                        has_max=has_max if ("Integer" in rule_type or "Decimal" in rule_type) else False,
                        max_val=max_val,
                    )
                    if err:
                        st.sidebar.error(err)
                    else:
                        if rule is None:
                            current_rules.pop(selected_col, None)
                        else:
                            current_rules[selected_col] = rule
                        st.session_state["rules"] = current_rules
                        st.rerun()

            with c_remove:
                if st.button("Delete Rule", use_container_width=True):
                    current_rules.pop(selected_col, None)
                    clear_column_widget_state(st.session_state, selected_col)
                    st.session_state["rules"] = current_rules
                    st.rerun()

    # Active rules display
    if current_rules:
        st.sidebar.markdown("**Active Rules:**")
        for col_name, rule in current_rules.items():
            st.sidebar.info(f"**{col_name}**: {rule.describe()}")
        if st.sidebar.button("Clear All Rules"):
            clear_all_rule_widget_states(st.session_state)
            st.session_state["rules"] = {}
            st.rerun()
    else:
        st.sidebar.caption("No custom rules active. All columns are evaluated on completeness & uniqueness.")

    st.sidebar.divider()
    st.sidebar.caption("DataSentinel Engine v1.0 • Built with Python & Streamlit")
    return current_rules


def render_score_card(label: str, score: float, subtitle: str, color_threshold: float = 80.0):
    """Renders a styled metric card."""
    color = get_score_color(score, color_threshold)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="score-label">{label}</div>
            <div class="score-badge" style="color: {color};">{score:0.1f}%</div>
            <div style="font-size: 0.8rem; color: #6c757d;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.title("🛡️ DataSentinel — Data Quality & Observability")
    st.markdown(
        "Audit tabular CSV datasets in real time for **completeness**, **validity**, "
        "and **uniqueness** with transparent, explainable scoring."
    )

    # Dataset Source Selection
    source_choice = st.radio(
        "Choose Data Source:",
        options=["Use Included Demo (sample.csv)", "Upload CSV File"],
        horizontal=True,
    )

    file_bytes: Optional[bytes] = None
    display_name: str = ""

    if source_choice == "Use Included Demo (sample.csv)":
        demo_path = get_default_demo_path()
        if not demo_path.exists():
            st.error("Demo file `sample.csv` not found in project directory.")
            return
        with open(demo_path, "rb") as f:
            file_bytes = f.read()
        display_name = "sample.csv"
        dataset_key = "demo_sample.csv"
    else:
        uploaded_file = st.file_uploader(
            "Upload a CSV dataset",
            type=["csv"],
            help="Upload any standard CSV file with column headers.",
        )
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            display_name = uploaded_file.name
            dataset_key = f"upload_{uploaded_file.name}_{len(file_bytes)}"
        else:
            dataset_key = "no_upload"

    # Reset rules when switching between distinct datasets
    if "last_dataset_key" not in st.session_state or st.session_state["last_dataset_key"] != dataset_key:
        st.session_state["last_dataset_key"] = dataset_key
        clear_all_rule_widget_states(st.session_state)
        # For demo dataset, seed default age rule; otherwise reset rules
        if source_choice == "Use Included Demo (sample.csv)":
            st.session_state["rules"] = {"age": ColumnRule(column="age", data_type="int", min_value=0, max_value=120)}
        else:
            st.session_state["rules"] = {}

    if file_bytes is None:
        # Clean Empty State
        st.divider()
        st.info("👋 **Welcome to DataSentinel!** Select the Demo dataset above or upload your own CSV file to start auditing.")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("#### 1. Ingest & Normalize")
            st.write("Safely handles UTF-8 BOM, malformed lines, and arbitrary CSV schemas.")
        with c2:
            st.markdown("#### 2. Configure Rules")
            st.write("Set column type checks and numeric boundaries or run unconstrained.")
        with c3:
            st.markdown("#### 3. Transparent Audit")
            st.write("Inspect exact row numbers for duplicates, nulls, and rule violations.")
        return

    # Extract column names quickly from headers without auditing the full dataset twice
    detected_cols = extract_column_names(file_bytes)

    # Render sidebar with discovered columns to allow interactive rule configuration
    active_rules = render_sidebar(detected_cols)

    # Execute single audit pass with active rules
    report = run_audit(file_bytes, display_name, active_rules)

    if report is None:
        return

    st.divider()

    # Top Overview Metrics
    st.subheader(f"📊 Dataset Quality Overview: `{display_name}`")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_score_card(
            label="Overall DQ Score",
            score=report.scores.overall,
            subtitle="Weighted Quality Score",
        )
    with m2:
        render_score_card(
            label="Completeness (35%)",
            score=report.scores.completeness,
            subtitle=f"{report.missing_values_count} missing cells",
        )
    with m3:
        render_score_card(
            label="Validity (35%)",
            score=report.scores.validity,
            subtitle=f"{report.invalid_values_count} rule violations",
        )
    with m4:
        render_score_card(
            label="Uniqueness (30%)",
            score=report.scores.uniqueness,
            subtitle=f"{report.duplicate_rows_count} duplicate rows",
        )

    # Dataset metadata summary
    st.caption(
        f"**Records:** {report.total_rows:,} rows • "
        f"**Columns:** {report.total_columns} ({', '.join(report.column_names)}) • "
        f"**Total Findings:** {len(report.issues)} issue(s)"
    )

    # Transparent Scoring Methodology Expander
    with st.expander("ℹ️ How is this score calculated? (Transparent Scoring Model)", expanded=False):
        st.markdown(
            r"""
            **Overall Data Quality Formula:**
            $$Score_{overall} = (0.35 \times Completeness) + (0.35 \times Validity) + (0.30 \times Uniqueness)$$
            
            - **Completeness ($35\%$)**: $\frac{\text{Total Cells} - \text{Missing Cells}}{\text{Total Cells}} \times 100$. Blank and whitespace-only cells count as missing.
            - **Validity ($35\%$)**: $\frac{\text{Evaluated Cells} - \text{Invalid Cells}}{\text{Evaluated Cells}} \times 100$. Evaluated on columns with configured rules. Unconfigured columns have no constraints and do not dilute the validity denominator.
            - **Uniqueness ($30\%$)**: $\frac{\text{Total Rows} - \text{Duplicate Rows}}{\text{Total Rows}} \times 100$. The first occurrence of a record is unique; subsequent identical rows increment the duplicate count.
            - **Empty Datasets**: An empty dataset or header-only file receives $0.0\%$ across all dimensions.
            
            *Note: This is DataSentinel's heuristic quality model designed for clear observability, not an arbitrary industry standard.*
            """
        )

    # Tabs for detailed inspection
    tab_findings, tab_columns, tab_export = st.tabs(["🔍 Findings Explorer", "📋 Column Metrics", "📥 Export Report"])

    # TAB 1: Findings Explorer
    with tab_findings:
        if not report.issues:
            st.success("🎉 **No quality issues detected!** All records meet the configured quality criteria.")
        else:
            st.markdown(f"**Found {len(report.issues)} issue(s) across the dataset:**")
            
            # Interactive filtering controls
            f_col1, f_col2 = st.columns([1, 1])
            with f_col1:
                available_types = sorted(list(set(i.issue_type for i in report.issues)))
                selected_types = st.multiselect("Filter by Issue Type", options=available_types, default=available_types)
            with f_col2:
                available_cols = sorted(list(set(i.column for i in report.issues if i.column)))
                col_filter_options = ["(All Columns)"] + available_cols
                selected_col_filter = st.selectbox("Filter by Column", options=col_filter_options)

            # Filter findings
            filtered_issues = [
                i for i in report.issues
                if i.issue_type in selected_types
                and (selected_col_filter == "(All Columns)" or i.column == selected_col_filter)
            ]

            if not filtered_issues:
                st.info("No findings match the selected filters.")
            else:
                table_rows = []
                for issue in filtered_issues:
                    table_rows.append({
                        "Row Number": f"Row {issue.row_number}" if issue.row_number is not None else "Dataset",
                        "Column": issue.column or "—",
                        "Issue Type": issue.issue_type.replace("_", " ").title(),
                        "Observed Value": str(issue.value) if issue.value is not None else "—",
                        "Explanation": issue.message,
                    })
                st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # TAB 2: Column Metrics
    with tab_columns:
        if not report.column_summaries:
            st.info("No columns available to display.")
        else:
            col_data = []
            for col_name, summary in report.column_summaries.items():
                col_data.append({
                    "Column Name": col_name,
                    "Total Cells": summary.total_cells,
                    "Missing Cells": summary.missing_count,
                    "Completeness": f"{summary.completeness_score:0.1f}%",
                    "Invalid Values": summary.invalid_count,
                    "Active Validation Rule": summary.rule_description or "Unconstrained",
                })
            st.dataframe(col_data, use_container_width=True, hide_index=True)

    # TAB 3: Export Report
    with tab_export:
        st.markdown("#### Download Sanitized Audit Report")
        st.write("Export the complete quality evaluation as a JSON document. Local file paths and system details are automatically sanitized.")
        
        json_report_str = report_to_json(report, display_name=display_name)
        download_name = build_download_filename(display_name)

        st.download_button(
            label="⬇️ Download Quality Report (JSON)",
            data=json_report_str,
            file_name=download_name,
            mime="application/json",
            type="primary",
        )

        with st.expander("Preview JSON Export", expanded=False):
            st.json(json.loads(json_report_str))


if __name__ == "__main__":
    main()

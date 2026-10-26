# DataSentinel

DataSentinel is a lightweight, reliable, and transparent data quality and observability platform designed to audit tabular CSV datasets before they are ingested into production pipelines, analytical warehouses, or machine learning models.

---

## 1. Current Functionality

- **Dual Interfaces**:
  - **Interactive Streamlit Web Dashboard (`app.py`)**: Drag-and-drop CSV upload, interactive demo dataset (`sample.csv`), live rule configuration, metric score cards, findings explorer with multi-criteria filters, and one-click JSON report download.
  - **Scriptable CLI (`main.py`)**: Terminal auditor with progress indicators, column-level summaries, and human-readable findings.
- **Safe CSV Ingestion**: Loads CSV files using `utf-8-sig` encoding (supporting UTF-8 BOM and non-ASCII text) and normalizes malformed rows (column count mismatches) without crashing.
- **Completeness Auditing**: Detects missing, empty (`""`), and whitespace-only (`"   "`) cells across all columns in any arbitrary CSV.
- **Uniqueness Auditing**: Identifies exact duplicate rows across all fields, reports the specific duplicate CSV line numbers (1-indexed), and references the original row number.
- **Configurable Validation Rules**: Supports modular column rules for type checks (`int`, `float`, `str`) and numeric range constraints (`min_value`, `max_value`) without hardcoding schema details into the engine.
- **Transparent Dimension Scoring**: Computes objective scores ($0.0$ to $100.0$) for Completeness, Validity, and Uniqueness, aggregated into a weighted overall Data Quality Score.
- **Sanitized Report Export**: Safely exports complete audit results as JSON (`report_to_json`), automatically stripping local disk paths and protecting user confidentiality.

---

## 2. Project Structure

```
datasentinel/
├── .gitignore               # Ignored caches, virtual environments, reports, and secrets
├── README.md                # Project documentation and scoring specification
├── requirements.txt         # Minimal runtime dependencies (Streamlit)
├── sample.csv               # Existing test dataset (preserved)
├── main.py                  # CLI entry point and terminal report renderer
├── app.py                   # Streamlit interactive web dashboard
├── core/                    # Core Data Quality Engine
│   ├── __init__.py          # Public package API exports
│   ├── models.py            # Dataclasses: QualityReport, QualityIssue, DimensionScores, ColumnSummary
│   ├── rules.py             # Configurable column validation rules (type & range checks)
│   ├── loader.py            # Safe CSV reader (UTF-8 BOM, malformed rows, file errors)
│   ├── analyzer.py          # Analysis pipeline and transparent scoring engine
│   ├── dashboard_helpers.py # Streamlit UI state management and header extraction helpers
│   └── export.py            # Sanitized report serialization and JSON export helpers
└── tests/                   # Automated Test Suite (Unittest & Pytest compatible)
    ├── __init__.py
    ├── test_dashboard_helpers.py # Tests for UI helpers, widget isolation, and in-memory audit
    ├── test_loader.py       # Tests for empty files, BOM, malformed rows, missing files
    ├── test_rules.py        # Tests for type validation, range bounds, unconfigured rules
    ├── test_scoring.py      # Tests for dimension scores, empty datasets, duplicate counts
    ├── test_export.py       # Tests for path sanitization, dict serialization, and JSON exports
    └── test_analyzer.py     # End-to-end integration tests on sample and synthetic datasets
```

---

## 3. Scoring Methodology & Mathematical Model

> [!NOTE]
> DataSentinel's scoring model is an explicit heuristic evaluation framework designed to provide transparent, explainable metrics for data engineers. It is not an arbitrary or universal industry standard.

### Quality Dimension Formulas

#### 1. Completeness ($S_c$) — Default Weight: 35%
Measures the proportion of expected data cells that contain valid, non-blank values.
- **Grid Total ($T$)**: $\text{Total Rows } (R) \times \text{Total Columns } (C)$
- **Missing Cells ($M$)**: Any cell where value is empty string `""` or whitespace-only `"   "`.
- **Formula**:
  $$S_c = \frac{T - M}{T} \times 100$$
- **Empty Dataset Rule**: If $R = 0$ or $C = 0$, $S_c = 0.0\%$.

#### 2. Validity ($S_v$) — Default Weight: 35%
Measures the proportion of rule-evaluated values that satisfy their configured constraints (data type and numeric boundaries).
- **Evaluated Cells ($T_{eval}$)**: Count of non-blank cells belonging to columns with an active `ColumnRule`.
- **Invalid Cells ($I$)**: Count of cells failing type parsing or exceeding range boundaries.
- **Formula**:
  $$S_v = \begin{cases} \frac{T_{eval} - I}{T_{eval}} \times 100 & \text{if } T_{eval} > 0 \\ 100.0\% & \text{if no rules configured} \end{cases}$$
- **Unconfigured Columns**: Columns without rules are treated as unconstrained. Their cells are excluded from $T_{eval}$ so they do not artificially dilute or inflate the score of columns with explicit constraints.
- **Empty Dataset Rule**: If $R = 0$, $S_v = 0.0\%$.

#### 3. Uniqueness ($S_u$) — Default Weight: 30%
Measures the proportion of distinct records in the dataset.
- **Total Rows ($R$)**: Total data rows (excluding the header row).
- **Duplicate Rows ($D$)**: Number of rows whose complete column tuple matches an earlier row. The first instance is retained as unique; only subsequent identical rows increment $D$.
- **Formula**:
  $$S_u = \frac{R - D}{R} \times 100$$
- **Empty Dataset Rule**: If $R = 0$, $S_u = 0.0\%$.

#### 4. Overall Data Quality Score ($S_{overall}$)
Weighted linear combination of the three dimensions:
$$S_{overall} = (0.35 \times S_c) + (0.35 \times S_v) + (0.30 \times S_u)$$
Bounded between $0.0$ and $100.0$, rounded to 2 decimal places. If $R = 0$, $S_{overall} = 0.0$.

---

## 4. Installation & Setup

### Supported Python Version
- **Python 3.9+** (tested and verified up through **Python 3.13**).
- The core data quality engine (`core/`), CLI (`main.py`), and test suite (`tests/`) rely exclusively on the Python standard library (`dataclasses`, `csv`, `pathlib`, `typing`, `math`).
- The interactive web dashboard (`app.py`) requires `streamlit>=1.28.0`.

### Step 1: Clone and Enter the Repository

```bash
git clone https://github.com/thakurbarkha802-wq/data-sentinel.git
cd data-sentinel
```

### Step 2: Create and Activate a Virtual Environment

- **On Windows (Command Prompt / PowerShell)**:
  ```powershell
  python -m venv .venv
  .venv\Scripts\activate
  ```

- **On macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### Step 3: Install Dependencies

Install the minimal runtime dependencies:
```bash
python -m pip install -r requirements.txt
```

---

## 5. Run & Test Instructions

### Running the Terminal CLI

Audit the default `sample.csv` dataset:
```bash
python main.py
```

Audit an arbitrary CSV file:
```bash
python main.py path/to/your_dataset.csv
```

### Running the Interactive Web Dashboard

Launch the Streamlit web application:
```bash
python -m streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### Exporting Results

- **From the Interactive Web Dashboard**:
  1. Upload a CSV file or load the sample dataset.
  2. Configure any optional column validation rules.
  3. Navigate to the **📥 Export Report** tab in the main view.
  4. Optionally inspect the sanitized JSON payload in the **Preview JSON Export** expander.
  5. Click **⬇️ Download Quality Report (JSON)** to save `datasentinel_report_<dataset_name>.json`.
  *(All local disk paths and system details are automatically stripped to protect confidentiality.)*

- **From the Terminal CLI**:
  Redirect standard output to persist the terminal audit report:
  ```bash
  python main.py sample.csv > audit_report.txt
  ```

### Running the Automated Test Suite

- **Primary Test Runner (Built-in `unittest`)**:
  Zero external test dependencies required. Runs all 56 unit and integration tests:
  ```bash
  python -m unittest discover -s tests -v
  ```

- **Alternative Runner (`pytest`)**:
  If `pytest` is installed in your development environment:
  ```bash
  pytest tests/ -v
  ```

---

## 6. Current Limitations

1. **File Format**: Only tabular `.csv` files are currently parsed (Excel `.xlsx`, Parquet, and SQL connections are not yet supported).
2. **Rule Persistence**: Interactive rules in the dashboard persist within the current session, but cannot yet be imported from or saved to external YAML/JSON configuration files.
3. **Automated Remediation**: DataSentinel detects, flags, and scores data quality issues, but does not mutate or rewrite the original dataset.
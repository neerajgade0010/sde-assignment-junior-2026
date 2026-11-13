# Assignment A — Interaction Ledger & Reporting Pipeline

## 1. Overview

This project implements a data ingestion and reporting pipeline using Python and SQLite.

It processes lead CSV files and event JSONL files from multiple data drops, validates and normalizes input data, protects personally identifiable information (PII), links events to leads, and generates the required reports.

## 2. Technologies Used

- Python
- SQLite
- Pandas (if used by the implementation)
- Cryptography (Fernet encryption)
- HMAC hashing
- Pytest

## 3. Project Structure

```text
sde-assignment-junior-2026/
├── assignment-a-data/
│   └── schemas/
├── data/
│   ├── drop_1/
│   └── drop_2/
├── solution/
│   ├── database.py
│   ├── validation.py
│   ├── schema_loader.py
│   ├── security.py
│   ├── lead_ingestion.py
│   ├── event_ingestion.py
│   ├── reports.py
│   ├── generate_reports.py
│   ├── requirements.txt
│   ├── tests/
│   └── reports/
├── SUBMISSION.md
└── AI_USAGE.md
```

## 4. Setup Instructions

Open a terminal in the `solution` directory.

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## 5. Data Ingestion

Run the following commands from the `solution` directory.

### Step 1: Ingest Drop 1 leads

```powershell
python -c "from lead_ingestion import ingest_leads; ingest_leads('../data/drop_1')"
```

### Step 2: Ingest Drop 1 events

```powershell
python -c "from event_ingestion import ingest_events; ingest_events('../data/drop_1')"
```

### Step 3: Ingest Drop 2 leads

```powershell
python -c "from lead_ingestion import ingest_leads; ingest_leads('../data/drop_2')"
```

### Step 4: Ingest Drop 2 events

```powershell
python -c "from event_ingestion import ingest_events; ingest_events('../data/drop_2')"
```

The event ingestion process performs a final event re-linking pass, allowing previously orphaned events to be linked when their corresponding leads become available.

## 6. Generate Reports

From the `solution` directory, execute:

```powershell
python generate_reports.py
```

The generated reports are saved in:

```text
solution/reports/
```

The five output files are:

- `batch_summary.csv`
- `daily_overview.csv`
- `lead_report.csv`
- `rejections.csv`
- `data_quality.json`

## 7. Run Tests

Run the complete test suite:

```powershell
python -m pytest -v
```

The implementation's current test suite contains 33 tests, all of which passed during development.

## 8. Data Security

The implementation uses encryption for sensitive lead information and deterministic HMAC hashing for phone-based matching.

Generated encryption keys are stored locally and should not be committed to version control.

## 9. Idempotency

The ingestion process maintains file-ingestion records to prevent already processed files from being processed again.

## 10. Output

All five required reports are generated from the SQLite database after ingestion is complete.
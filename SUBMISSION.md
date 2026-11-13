# Submission

## Candidate

- **Name:** Neeraj Gade
- **Assignment chosen:** A — Interaction Ledger & Reporting Pipeline
- **Time spent (honest estimate):** [Fill in your actual total time]

## How to Run

The following commands use Windows PowerShell and assume Python 3.11 or later is installed.

### 1. Clone the repository

```powershell
git clone https://github.com/neerajgade0010/sde-assignment-junior-2026.git
cd sde-assignment-junior-2026
```

### 2. Create and generate the input data

The generated data is intentionally not committed to the repository.

```powershell
python assignment-a-data/tools/generate_data.py --seed 42 --scale small --out data
```

### 3. Set up the Python environment

```powershell
cd solution
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Ingest Drop 1

Run the lead ingestion before the event ingestion:

```powershell
python -c "from lead_ingestion import ingest_leads; ingest_leads('../data/drop_1')"
python -c "from event_ingestion import ingest_events; ingest_events('../data/drop_1')"
```

### 5. Ingest Drop 2

```powershell
python -c "from lead_ingestion import ingest_leads; ingest_leads('../data/drop_2')"
python -c "from event_ingestion import ingest_events; ingest_events('../data/drop_2')"
```

### 6. Generate the reports

```powershell
python generate_reports.py
```

The five report files are generated in `solution/reports/`:

- `batch_summary.csv`
- `daily_overview.csv`
- `lead_report.csv`
- `rejections.csv`
- `data_quality.json`

### 7. Run the tests

```powershell
python -m pytest -v
```

The local development test run completed with 33 passing tests.

## Design

### Architecture

The implementation is organized into separate Python modules:

- `schema_loader.py`: loads workflow schemas and maps input headers to schema fields.
- `validation.py`: normalizes and validates lead values.
- `security.py`: encrypts sensitive values and creates deterministic phone hashes.
- `database.py`: manages the SQLite database and its tables.
- `lead_ingestion.py`: processes lead CSV files, rejects invalid rows, and merges duplicate leads.
- `event_ingestion.py`: processes JSONL event files, handles duplicate events, links events to leads, and re-links events when leads arrive later.
- `reports.py`: derives call and lead information and generates the required reports.
- `generate_reports.py`: provides the report-generation entry point.

### Database design

SQLite is used as the persistent database.

The database contains the following tables:

- `leads`: stores normalized lead records and encrypted PII.
- `events`: stores the interaction event ledger.
- `event_links`: stores the association between events and leads.
- `rejections`: stores rejected lead rows and their reasons without storing PII.
- `ingested_files`: tracks processed input files to support idempotent ingestion.
- `pipeline_stats`: stores pipeline data-quality counters.

The event ledger is append-only. Event linking is maintained separately so that events received before their corresponding leads can be linked when the leads arrive in a later drop.

### PII protection

Sensitive lead values are encrypted using Fernet encryption.

Phone numbers are matched using deterministic HMAC hashes. This allows event-to-lead matching without storing plaintext phone numbers for matching purposes.

Encryption keys are generated and kept locally. They are excluded from version control.

### Report generation

Reports are derived from the stored leads, linked events, and disposition catalogue. Call counts require a linked `call.initiated` event. Effective dispositions account for supervisor overrides, and timestamps are interpreted in IST for report dates.

## Decisions & Assumptions

| Decision | Why | Alternative considered |
|---|---|---|
| Use SQLite | It provides persistent relational storage without requiring a separate database server and is allowed by the assignment. | PostgreSQL |
| Use Fernet encryption for PII | Sensitive values need to remain encrypted at rest while still being available to authorized application code. | Plaintext storage or reversible custom encryption |
| Use deterministic HMAC hashes for phone matching | Events must be matched to leads without using plaintext phone numbers as database lookup keys. | Storing plaintext phone numbers for matching |
| Keep event records separate from event-to-lead links | Events can arrive before leads, so links need to be established or refreshed later without rewriting the event ledger. | Storing all event and lead information in one table |
| Track processed files | Re-ingesting an already processed drop should not duplicate its records or counters. | Reprocessing all files on every run |

## Failure Modes Considered

- Invalid lead rows are rejected with a reason.
- Invalid optional values are handled as null values and counted as field warnings.
- Duplicate leads are merged using the workflow and normalized phone identity.
- Duplicate event IDs are detected across ingested drops.
- Malformed event lines are counted and skipped.
- Events that cannot yet be linked are retained for later linking.
- Database file processing uses transactions so a failed file can be rolled back.
- Previously processed files are tracked to prevent duplicate ingestion.
- Sensitive lead information is encrypted, and generated key files are excluded from Git.

### Known limitations

- Large-scale performance has not been benchmarked.
- The implementation has been tested with the supplied small dataset; additional testing with unseen seeds and larger datasets would provide stronger confidence.
- The local encryption key must be preserved securely. Losing it prevents decryption of data encrypted with that key.
- A production deployment would need managed key storage, backups, monitoring, and a recovery procedure.

## Testing

The test suite was run using:

```powershell
python -m pytest -v
```

The local development run completed with **33 passing tests**.

The tests cover validation, schema loading, encryption and hashing, event ingestion, and reporting logic.

The generated reports were also inspected manually for their expected headers, sample values, date formatting, phone masking, and connectivity-rate calculations.

## Results

The supplied small dataset was processed locally.

Observed data-quality counters from the completed run:

| Metric | Result |
|---|---:|
| Lead rows processed | 2,057 |
| Lead rows rejected | 108 |
| Duplicate lead rows merged | 57 |
| Field warnings | 122 |
| Event lines processed | 8,745 |
| Malformed events | 8 |
| Duplicate events dropped | 237 |
| Final orphan events | 462 |
| Unknown disposition events | 18 |

All five required report files were generated and inspected.

No large-scale performance timing is claimed because a large-dataset benchmark was not performed.

## If I Had Another Day

1. Run the pipeline against additional generator seeds and compare all report outputs with expected results.
2. Add more integration tests covering the complete pipeline from raw input files to generated reports.
3. Review edge cases around unknown dispositions, orphan re-linking, and event ordering.
4. Benchmark ingestion and reporting with the large dataset.
5. Improve operational logging and document a production recovery and key-management approach.
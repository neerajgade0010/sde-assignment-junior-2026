
import csv
import json
import hashlib

from pathlib import Path
from datetime import datetime, timezone

from database import get_connection
from schema_loader import load_schema, map_headers
from validation import normalize_field_value
from security import encrypt_value, create_phone_hash


def current_timestamp():
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def increment_stat(connection, metric, amount=1):
    """
    Increase a data-quality counter.
    """

    connection.execute(
        """
        INSERT INTO pipeline_stats (metric, value)
        VALUES (?, ?)
        ON CONFLICT(metric)
        DO UPDATE SET value = value + excluded.value
        """,
        (metric, amount)
    )


def get_file_hash(file_path):
    """Calculate SHA-256 hash of a file."""

    file_hash = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            file_hash.update(chunk)

    return file_hash.hexdigest()


def is_blank_row(row):
    """Check whether every cell in a CSV row is empty."""

    return all(not str(value).strip() for value in row)


def validate_lead_row(row, header_mapping, schema):
    """
    Validate one customer row using the workflow schema.

    Returns:
        (normalised_values, rejection_reason, warning_count)
    """

    values = {}
    warning_count = 0

    for field in schema["fields"]:

        field_name = field["name"]

        column_index = header_mapping.get(field_name)

        if column_index is None or column_index >= len(row):
            raw_value = None
        else:
            raw_value = row[column_index]

        # Trim whitespace.
        if raw_value is not None:
            raw_value = str(raw_value).strip()

        # Empty values count as missing.
        if not raw_value:

            if field.get("required", False):
                return (
                    None,
                    f"missing_required:{field_name}",
                    0
                )

            values[field_name] = None
            continue

        try:

            normalised_value = normalize_field_value(
                field,
                raw_value
            )

            values[field_name] = normalised_value

        except ValueError:

            if field.get("required", False):

                if field["type"] == "phone":
                    reason = "invalid_phone"
                else:
                    reason = f"invalid_{field_name}"

                return None, reason, 0

            # Invalid optional fields become null.
            values[field_name] = None
            warning_count += 1

    return values, None, warning_count


def save_lead(connection, workflow_id, batch_id, values, schema):
    """
    Insert a new lead or merge it with an existing lead.

    Customer identity:
        (workflow_id, canonical phone)
    """

    phone = values["phone"]

    phone_hash = create_phone_hash(phone)

    phone_encrypted = encrypt_value(phone)

    customer_name_encrypted = encrypt_value(
        values["customer_name"]
    )

    # Find the external reference field from the schema.
    reference_field = next(
        field["name"]
        for field in schema["fields"]
        if field.get("reference", False)
    )

    external_ref = values[reference_field]

    # Only non-PII fields are stored in fields_json.
    non_pii_fields = {
        field["name"]
        for field in schema["fields"]
        if not field.get("pii", False)
        and field["name"] not in ("customer_name", "phone")
    }

    new_fields = {
        key: values.get(key)
        for key in non_pii_fields
    }

    existing = connection.execute(
        """
        SELECT lead_id, fields_json
        FROM leads
        WHERE workflow_id = ?
          AND phone_hash = ?
        """,
        (workflow_id, phone_hash)
    ).fetchone()

    timestamp = current_timestamp()

    if existing is None:

        connection.execute(
            """
            INSERT INTO leads (
                workflow_id,
                external_ref,
                batch_id,
                phone_hash,
                phone_encrypted,
                customer_name_encrypted,
                fields_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workflow_id,
                external_ref,
                batch_id,
                phone_hash,
                phone_encrypted,
                customer_name_encrypted,
                json.dumps(new_fields),
                timestamp,
                timestamp
            )
        )

        return "inserted"

    # Existing lead: merge only non-null incoming values.
    lead_id = existing["lead_id"]

    merged_fields = json.loads(existing["fields_json"])

    for key, value in new_fields.items():

        if value is not None:
            merged_fields[key] = value

    connection.execute(
        """
        UPDATE leads
        SET
            external_ref = ?,
            phone_encrypted = ?,
            customer_name_encrypted = ?,
            fields_json = ?,
            updated_at = ?
        WHERE lead_id = ?
        """,
        (
            external_ref,
            phone_encrypted,
            customer_name_encrypted,
            json.dumps(merged_fields),
            timestamp,
            lead_id
        )
    )

    increment_stat(
        connection,
        "duplicate_lead_rows_merged"
    )

    return "merged"


def apply_defaults(connection, workflow_id, schema):
    """
    Apply schema defaults after merging.

    Existing non-null values are never overwritten.
    """

    defaults = {
        field["name"]: field["default"]
        for field in schema["fields"]
        if "default" in field
    }

    if not defaults:
        return

    leads = connection.execute(
        """
        SELECT lead_id, fields_json
        FROM leads
        WHERE workflow_id = ?
        """,
        (workflow_id,)
    ).fetchall()

    for lead in leads:

        fields = json.loads(lead["fields_json"])

        changed = False

        for field_name, default_value in defaults.items():

            if fields.get(field_name) is None:
                fields[field_name] = default_value
                changed = True

        if changed:

            connection.execute(
                """
                UPDATE leads
                SET fields_json = ?, updated_at = ?
                WHERE lead_id = ?
                """,
                (
                    json.dumps(fields),
                    current_timestamp(),
                    lead["lead_id"]
                )
            )


def process_csv_file(
    connection,
    csv_path,
    drop_name,
    drop_root,
    workflow_id,
    schema
):
    """
    Process one CSV file.

    The file is processed in its original row order.
    """

    batch_id = csv_path.stem

    relative_path = str(
        csv_path.relative_to(drop_root)
    )

    file_hash = get_file_hash(csv_path)

    # Skip files already processed.
    existing_file = connection.execute(
        """
        SELECT file_id
        FROM ingested_files
        WHERE drop_name = ?
          AND relative_path = ?
        """,
        (drop_name, relative_path)
    ).fetchone()

    if existing_file:

        print(f"Skipping already processed: {relative_path}")

        return {
            "status": "skipped",
            "rows": 0,
            "inserted": 0,
            "merged": 0,
            "rejected": 0,
            "warnings": 0
        }

    inserted = 0
    merged = 0
    rejected = 0
    warnings = 0
    row_number = 0

    with open(
        csv_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.reader(file)

        headers = next(reader, None)

        if headers is not None:

            header_mapping = map_headers(headers, schema)

            for row in reader:

                # Completely blank rows are ignored.
                if is_blank_row(row):
                    continue

                row_number += 1

                increment_stat(
                    connection,
                    "lead_rows_total"
                )

                values, rejection_reason, row_warnings = (
                    validate_lead_row(
                        row,
                        header_mapping,
                        schema
                    )
                )

                if rejection_reason:

                    connection.execute(
                        """
                        INSERT INTO rejections (
                            workflow_id,
                            batch_id,
                            row_number,
                            reason
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            workflow_id,
                            batch_id,
                            row_number,
                            rejection_reason
                        )
                    )

                    increment_stat(
                        connection,
                        "lead_rows_rejected"
                    )

                    rejected += 1

                    continue

                # Warnings are counted only for accepted rows.
                if row_warnings:

                    increment_stat(
                        connection,
                        "field_warnings",
                        row_warnings
                    )

                    warnings += row_warnings

                result = save_lead(
                    connection,
                    workflow_id,
                    batch_id,
                    values,
                    schema
                )

                if result == "inserted":
                    inserted += 1
                else:
                    merged += 1

    # Apply defaults after processing and merging this file.
    apply_defaults(
        connection,
        workflow_id,
        schema
    )

    # Record the file only after successful processing.
    connection.execute(
        """
        INSERT INTO ingested_files (
            drop_name,
            relative_path,
            file_hash,
            file_type,
            processed_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            drop_name,
            relative_path,
            file_hash,
            "leads",
            current_timestamp()
        )
    )

    return {
        "status": "processed",
        "rows": row_number,
        "inserted": inserted,
        "merged": merged,
        "rejected": rejected,
        "warnings": warnings
    }


def ingest_leads(drop_path):
    """
    Ingest all lead CSV files inside a drop.

    Files are processed in filename order.
    """

    drop_root = Path(drop_path).resolve()

    leads_root = drop_root / "leads"

    if not leads_root.exists():
        raise FileNotFoundError(
            f"Leads directory not found: {leads_root}"
        )

    drop_name = drop_root.name

    overall_summary = {
        "files_processed": 0,
        "files_skipped": 0,
        "rows": 0,
        "inserted": 0,
        "merged": 0,
        "rejected": 0,
        "warnings": 0
    }

    connection = get_connection()

    try:

        # Workflows are processed in sorted order.
        workflow_directories = sorted(
            path
            for path in leads_root.iterdir()
            if path.is_dir()
        )

        for workflow_directory in workflow_directories:

            workflow_id = workflow_directory.name

            schema = load_schema(workflow_id)

            # CSV files are processed in filename order.
            csv_files = sorted(
                workflow_directory.glob("*.csv"),
                key=lambda path: path.name
            )

            for csv_path in csv_files:

                try:

                    # Each file is an independent transaction.
                    with connection:

                        result = process_csv_file(
                            connection,
                            csv_path,
                            drop_name,
                            drop_root,
                            workflow_id,
                            schema
                        )

                    if result["status"] == "skipped":

                        overall_summary["files_skipped"] += 1

                    else:

                        overall_summary["files_processed"] += 1

                        for key in (
                            "rows",
                            "inserted",
                            "merged",
                            "rejected",
                            "warnings"
                        ):
                            overall_summary[key] += result[key]

                        print(
                            f"Processed {csv_path.name}: "
                            f"{result['inserted']} inserted, "
                            f"{result['merged']} merged, "
                            f"{result['rejected']} rejected"
                        )

                except Exception:

                    # The current file transaction is rolled back.
                    raise

        return overall_summary

    finally:

        connection.close()

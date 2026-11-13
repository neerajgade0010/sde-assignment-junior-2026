
import csv
import json
import hashlib

from pathlib import Path
from datetime import datetime, timezone, timedelta

from database import get_connection
from validation import normalize_phone
from security import encrypt_value, create_phone_hash


BASE_DIR = Path(__file__).resolve().parent

SCHEMA_DIR = (
    BASE_DIR.parent
    / "assignment-a-data"
    / "schemas"
)

# India Standard Time: UTC +05:30
# Fixed offset avoids missing timezone data on Windows.
IST = timezone(timedelta(hours=5, minutes=30))


def current_timestamp():
    """Return the current timestamp in IST."""

    return datetime.now(IST).isoformat()


def normalize_timestamp(value):
    """
    Convert UTC, offset and naive timestamps to IST.

    Naive timestamps are treated as IST.
    """

    if not value or not isinstance(value, str):
        raise ValueError("invalid_timestamp")

    value = value.strip()

    # Convert UTC suffix into an ISO-compatible offset.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    # Naive timestamps mean IST according to the assignment.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)

    return parsed.astimezone(IST).isoformat()


def load_dispositions():
    """
    Load the official disposition catalogue.

    Returns:
        {
            ("motor_renewal", "renewed"): {
                "is_terminal": True,
                "is_success": True
            }
        }
    """

    disposition_path = SCHEMA_DIR / "dispositions.csv"

    dispositions = {}

    with open(
        disposition_path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            workflow_id = row["workflow_id"].strip()
            code = row["code"].strip()

            dispositions[(workflow_id, code)] = {
                "is_terminal": row["is_terminal"].strip().lower() == "true",
                "is_success": row["is_success"].strip().lower() == "true"
            }

    return dispositions


def get_file_hash(file_path):
    """Calculate SHA-256 for a JSONL file."""

    file_hash = hashlib.sha256()

    with open(file_path, "rb") as file:

        for chunk in iter(lambda: file.read(65536), b""):
            file_hash.update(chunk)

    return file_hash.hexdigest()


def increment_stat(connection, metric, amount=1):
    """Increment a persistent pipeline counter."""

    connection.execute(
        """
        INSERT INTO pipeline_stats (metric, value)
        VALUES (?, ?)
        ON CONFLICT(metric)
        DO UPDATE SET value = value + excluded.value
        """,
        (metric, amount)
    )


def process_event(connection, event, drop_name, dispositions):
    """
    Store one valid JSON event.

    Duplicate event IDs are skipped.
    Original events are never modified or deleted.
    """

    event_id = str(event["event_id"]).strip()

    existing = connection.execute(
        "SELECT event_id FROM events WHERE event_id = ?",
        (event_id,)
    ).fetchone()

    if existing:

        increment_stat(
            connection,
            "duplicate_events_dropped"
        )

        return "duplicate"

    event_type = str(event.get("event_type", "")).strip()

    workflow_id = str(event.get("workflow_id", "")).strip()

    call_id = event.get("call_id")

    occurred_at = normalize_timestamp(
        event.get("occurred_at")
    )

    payload = event.get("payload", {})

    if not isinstance(payload, dict):
        payload = {}

    phone = event.get("phone")

    phone_hash = None
    phone_encrypted = None

    if phone is not None:

        # Encrypt even if the phone is invalid.
        phone_encrypted = encrypt_value(phone)

        try:

            canonical_phone = normalize_phone(phone)

            if canonical_phone:
                phone_hash = create_phone_hash(canonical_phone)

        except ValueError:

            # Invalid phone means the event cannot be linked
            # using phone identity.
            phone_hash = None

    # Store all syntactically valid events, including orphans.
    # Unknown dispositions are retained in the ledger but
    # excluded from effective-disposition calculations.
    connection.execute(
        """
        INSERT INTO events (
            event_id,
            event_type,
            workflow_id,
            call_id,
            occurred_at,
            phone_hash,
            phone_encrypted,
            payload_json,
            received_drop,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            workflow_id,
            call_id,
            occurred_at,
            phone_hash,
            phone_encrypted,
            json.dumps(payload),
            drop_name,
            current_timestamp()
        )
    )

    # Create a link record even if the customer is not found.
    connection.execute(
        """
        INSERT INTO event_links (
            event_id,
            lead_id,
            link_method,
            updated_at
        )
        VALUES (?, NULL, 'orphan', ?)
        """,
        (
            event_id,
            current_timestamp()
        )
    )

    # A disposition event must contain a known catalogue code
    # before it can contribute to reporting.
    if event_type in ("disposition.set", "disposition.override"):

        code = payload.get("disposition_code")

        if (workflow_id, code) not in dispositions:
            return "unknown_disposition"

    return "stored"


def relink_events(connection):
    """
    Re-link events whenever new leads arrive.

    Normal events link by workflow and phone fingerprint.
    Overrides link through another event belonging to
    the same workflow and call.
    """

    timestamp = current_timestamp()

    # First link all events that contain a valid phone.
    connection.execute(
        """
        UPDATE event_links

        SET
            lead_id = (
                SELECT l.lead_id
                FROM events e

                JOIN leads l
                    ON l.workflow_id = e.workflow_id
                    AND l.phone_hash = e.phone_hash

                WHERE e.event_id = event_links.event_id
                LIMIT 1
            ),

            link_method = 'phone',
            updated_at = ?

        WHERE event_id IN (
            SELECT event_id
            FROM events
            WHERE phone_hash IS NOT NULL
        )
        AND lead_id IS NULL
        """,
        (timestamp,)
    )

    # Overrides do not contain a phone.
    # Link them through another event of the same call.
    connection.execute(
        """
        UPDATE event_links

        SET
            lead_id = (
                SELECT other_link.lead_id

                FROM events override_event

                JOIN events other_event
                    ON other_event.workflow_id =
                       override_event.workflow_id

                    AND other_event.call_id =
                        override_event.call_id

                    AND other_event.event_id !=
                        override_event.event_id

                JOIN event_links other_link
                    ON other_link.event_id =
                       other_event.event_id

                WHERE override_event.event_id =
                      event_links.event_id

                  AND other_link.lead_id IS NOT NULL

                LIMIT 1
            ),

            link_method = 'call_id',
            updated_at = ?

        WHERE event_id IN (
            SELECT event_id
            FROM events
            WHERE event_type = 'disposition.override'
              AND call_id IS NOT NULL
        )
        AND lead_id IS NULL
        """,
        (timestamp,)
    )

    # Orphan count represents the current final state.
    orphan_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM event_links
        WHERE lead_id IS NULL
        """
    ).fetchone()[0]

    connection.execute(
        """
        UPDATE pipeline_stats
        SET value = ?
        WHERE metric = 'orphan_events'
        """,
        (orphan_count,)
    )

    # Count unknown dispositions only after checking links.
    dispositions = load_dispositions()

    events = connection.execute(
        """
        SELECT
            e.event_id,
            e.workflow_id,
            e.event_type,
            e.payload_json

        FROM events e

        JOIN event_links el
            ON el.event_id = e.event_id

        WHERE el.lead_id IS NOT NULL
          AND e.event_type IN (
              'disposition.set',
              'disposition.override'
          )
        """
    ).fetchall()

    unknown_count = 0

    for event in events:

        payload = json.loads(event["payload_json"])

        code = payload.get("disposition_code")

        if (
            event["workflow_id"],
            code
        ) not in dispositions:

            unknown_count += 1

    connection.execute(
        """
        UPDATE pipeline_stats
        SET value = ?
        WHERE metric = 'unknown_disposition_events'
        """,
        (unknown_count,)
    )


def process_event_file(
    connection,
    file_path,
    drop_root,
    drop_name,
    dispositions
):
    """
    Process one JSONL file line by line.
    """

    relative_path = str(
        file_path.relative_to(drop_root)
    )

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
            "lines": 0,
            "stored": 0,
            "malformed": 0,
            "duplicates": 0,
            "unknown": 0
        }

    file_hash = get_file_hash(file_path)

    stored = 0
    malformed = 0
    duplicates = 0
    unknown = 0
    lines = 0

    with open(
        file_path,
        "r",
        encoding="utf-8-sig"
    ) as file:

        for line in file:

            # Empty lines do not count.
            if not line.strip():
                continue

            lines += 1

            # Every non-empty line contributes to events_total.
            increment_stat(
                connection,
                "events_total"
            )

            try:

                event = json.loads(line)

            except json.JSONDecodeError:

                increment_stat(
                    connection,
                    "malformed_events"
                )

                malformed += 1
                continue

            # The specification requires an event_id.
            if (
                not isinstance(event, dict)
                or not event.get("event_id")
                or not str(event["event_id"]).strip()
            ):

                increment_stat(
                    connection,
                    "malformed_events"
                )

                malformed += 1
                continue

            result = process_event(
                connection,
                event,
                drop_name,
                dispositions
            )

            if result == "duplicate":
                duplicates += 1

            elif result == "unknown_disposition":
                unknown += 1

            else:
                stored += 1

    # Register file after successful processing.
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
            "events",
            current_timestamp()
        )
    )

    return {
        "status": "processed",
        "lines": lines,
        "stored": stored,
        "malformed": malformed,
        "duplicates": duplicates,
        "unknown": unknown
    }


def ingest_events(drop_path):
    """
    Ingest all JSONL event files from one drop.

    Files are processed in filename order.
    """

    drop_root = Path(drop_path).resolve()

    events_root = drop_root / "events"

    if not events_root.exists():
        raise FileNotFoundError(
            f"Events directory not found: {events_root}"
        )

    drop_name = drop_root.name

    summary = {
        "files_processed": 0,
        "files_skipped": 0,
        "lines": 0,
        "stored": 0,
        "malformed": 0,
        "duplicates": 0,
        "unknown": 0
    }

    dispositions = load_dispositions()

    connection = get_connection()

    try:

        event_files = sorted(
            events_root.glob("*.jsonl"),
            key=lambda path: path.name
        )

        for file_path in event_files:

            # Each file is processed in its own transaction.
            with connection:

                result = process_event_file(
                    connection,
                    file_path,
                    drop_root,
                    drop_name,
                    dispositions
                )

                # Re-link old orphans too.
                relink_events(connection)

            if result["status"] == "skipped":

                summary["files_skipped"] += 1

            else:

                summary["files_processed"] += 1

                for key in (
                    "lines",
                    "stored",
                    "malformed",
                    "duplicates",
                    "unknown"
                ):
                    summary[key] += result[key]

                print(
                    f"Processed {file_path.name}: "
                    f"{result['stored']} stored, "
                    f"{result['malformed']} malformed, "
                    f"{result['duplicates']} duplicates"
                )

        # Final relinking pass after all files.
        with connection:
            relink_events(connection)

        return summary

    finally:
        connection.close()

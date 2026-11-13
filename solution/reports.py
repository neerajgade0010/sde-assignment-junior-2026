
import csv
import json

from pathlib import Path
from collections import defaultdict
from datetime import datetime

from database import get_connection
from security import decrypt_value
from schema_loader import load_schema
from event_ingestion import load_dispositions


def get_bucket(calls, dispositions):
    """
    Determine the current bucket of a lead.

    Priority:
    1. No calls -> yet_to_reach_out
    2. Any terminal disposition -> completed
    3. Every call failed telephony -> in_progress_telephony_failed
    4. Otherwise -> in_progress_dialed
    """

    if not calls:
        return "yet_to_reach_out"

    for call in calls:

        disposition = call["effective_disposition"]

        if disposition:

            metadata = dispositions.get(
                (call["workflow_id"], disposition)
            )

            if metadata and metadata["is_terminal"]:
                return "completed"

    if all(call["telephony_failed"] for call in calls):
        return "in_progress_telephony_failed"

    return "in_progress_dialed"


def get_effective_disposition(events, workflow_id, dispositions):
    """
    Determine the effective disposition of one call.

    A valid supervisor override takes priority.
    Otherwise, use the latest valid agent disposition.
    """

    overrides = []
    agent_dispositions = []

    for event in events:

        event_type = event["event_type"]

        if event_type not in (
            "disposition.set",
            "disposition.override"
        ):
            continue

        payload = json.loads(event["payload_json"])

        code = payload.get("disposition_code")

        # Unknown disposition codes are ignored.
        if (workflow_id, code) not in dispositions:
            continue

        candidate = {
            "code": code,
            "occurred_at": event["occurred_at"]
        }

        if event_type == "disposition.override":
            overrides.append(candidate)

        else:
            agent_dispositions.append(candidate)

    if overrides:

        latest = max(
            overrides,
            key=lambda item: item["occurred_at"]
        )

        return latest["code"]

    if agent_dispositions:

        latest = max(
            agent_dispositions,
            key=lambda item: item["occurred_at"]
        )

        return latest["code"]

    return None


def build_calls(events, dispositions):
    """
    Build individual calls from the append-only event ledger.

    A call exists only when call.initiated is present
    and the event is linked to a valid lead.
    """

    grouped_events = defaultdict(list)

    for event in events:

        if event["call_id"] is None:
            continue

        key = (
            event["lead_id"],
            event["workflow_id"],
            event["call_id"]
        )

        grouped_events[key].append(event)

    calls_by_lead = defaultdict(list)

    for key, call_events in grouped_events.items():

        lead_id, workflow_id, call_id = key

        initiated_events = [
            event
            for event in call_events
            if event["event_type"] == "call.initiated"
        ]

        # Calls without a linked initiated event do not count.
        if not initiated_events:
            continue

        # Use the earliest initiation timestamp for this call.
        initiated_event = min(
            initiated_events,
            key=lambda event: event["occurred_at"]
        )

        connected = any(
            event["event_type"] == "call.connected"
            for event in call_events
        )

        telephony_failed = any(
            event["event_type"] == "call.telephony_failed"
            for event in call_events
        )

        effective_disposition = get_effective_disposition(
            call_events,
            workflow_id,
            dispositions
        )

        call = {
            "lead_id": lead_id,
            "workflow_id": workflow_id,
            "call_id": call_id,
            "initiated_at": initiated_event["occurred_at"],
            "connected": connected,
            "telephony_failed": telephony_failed,
            "effective_disposition": effective_disposition
        }

        calls_by_lead[lead_id].append(call)

    # Sort each customer's calls chronologically.
    for lead_id in calls_by_lead:

        calls_by_lead[lead_id].sort(
            key=lambda call: call["initiated_at"]
        )

    return calls_by_lead


def write_csv(file_path, headers, rows):
    """
    Write a CSV file with an exact header row.
    """

    with open(
        file_path,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.writer(file)

        writer.writerow(headers)

        writer.writerows(rows)


def generate_batch_summary(leads, calls_by_lead, dispositions, output_dir):
    """
    Generate batch_summary.csv.
    """

    buckets = defaultdict(lambda: {
        "total_leads": 0,
        "yet_to_reach_out": 0,
        "in_progress_telephony_failed": 0,
        "in_progress_dialed": 0,
        "completed": 0
    })

    for lead in leads:

        lead_id = lead["lead_id"]

        calls = calls_by_lead.get(lead_id, [])

        bucket = get_bucket(calls, dispositions)

        key = (
            lead["workflow_id"],
            lead["batch_id"]
        )

        buckets[key]["total_leads"] += 1
        buckets[key][bucket] += 1

    rows = []

    for (workflow_id, batch_id), counts in sorted(buckets.items()):

        rows.append([
            workflow_id,
            batch_id,
            counts["total_leads"],
            counts["yet_to_reach_out"],
            counts["in_progress_telephony_failed"],
            counts["in_progress_dialed"],
            counts["completed"]
        ])

    write_csv(
        output_dir / "batch_summary.csv",
        [
            "workflow_id",
            "batch_id",
            "total_leads",
            "yet_to_reach_out",
            "in_progress_telephony_failed",
            "in_progress_dialed",
            "completed"
        ],
        rows
    )


def generate_daily_overview(calls_by_lead, dispositions, output_dir):
    """
    Generate daily_overview.csv.

    One row per workflow per IST date.
    """

    daily = defaultdict(lambda: {
        "total_calls": 0,
        "connected_calls": 0,
        "success_leads": set()
    })

    for lead_id, calls in calls_by_lead.items():

        for call in calls:

            call_date = datetime.fromisoformat(
                call["initiated_at"]
            ).date().isoformat()

            key = (
                call["workflow_id"],
                call_date
            )

            daily[key]["total_calls"] += 1

            if call["connected"]:
                daily[key]["connected_calls"] += 1

            disposition = call["effective_disposition"]

            if disposition:

                metadata = dispositions.get(
                    (call["workflow_id"], disposition)
                )

                if metadata and metadata["is_success"]:
                    daily[key]["success_leads"].add(lead_id)

    rows = []

    for (workflow_id, date), values in sorted(daily.items()):

        total_calls = values["total_calls"]

        connected_calls = values["connected_calls"]

        connectivity_rate = (
            connected_calls / total_calls
        )

        rows.append([
            workflow_id,
            date,
            total_calls,
            connected_calls,
            f"{connectivity_rate:.4f}",
            len(values["success_leads"])
        ])

    write_csv(
        output_dir / "daily_overview.csv",
        [
            "workflow_id",
            "date",
            "total_calls",
            "connected_calls",
            "connectivity_rate",
            "success_leads"
        ],
        rows
    )


def generate_lead_report(
    leads,
    calls_by_lead,
    dispositions,
    output_dir
):
    """
    Generate lead_report.csv.
    """

    rows = []

    for lead in leads:

        lead_id = lead["lead_id"]

        calls = calls_by_lead.get(lead_id, [])

        bucket = get_bucket(calls, dispositions)

        encrypted_phone = lead["phone_encrypted"]

        phone = decrypt_value(encrypted_phone)

        # Mask the phone number.
        phone_masked = "+91******" + phone[-4:]

        last_call_at = ""

        current_disposition = None

        if calls:

            last_call_at = max(
                calls,
                key=lambda call: call["initiated_at"]
            )["initiated_at"]

            # Find the most recent call that has
            # an effective disposition.
            calls_with_disposition = [
                call
                for call in calls
                if call["effective_disposition"] is not None
            ]

            if calls_with_disposition:

                latest_disposition_call = max(
                    calls_with_disposition,
                    key=lambda call: call["initiated_at"]
                )

                current_disposition = (
                    latest_disposition_call["effective_disposition"]
                )

        connected_calls = sum(
            1 for call in calls if call["connected"]
        )

        ever_success = any(
            (
                call["effective_disposition"] is not None
                and dispositions.get(
                    (
                        call["workflow_id"],
                        call["effective_disposition"]
                    ),
                    {}
                ).get("is_success", False)
            )
            for call in calls
        )

        rows.append([
            lead["workflow_id"],
            lead["external_ref"],
            lead["batch_id"],
            phone_masked,
            bucket,
            len(calls),
            connected_calls,
            last_call_at,
            current_disposition or "",
            str(ever_success).lower()
        ])

    rows.sort(
        key=lambda row: (
            row[0],
            row[1] or ""
        )
    )

    write_csv(
        output_dir / "lead_report.csv",
        [
            "workflow_id",
            "external_ref",
            "batch_id",
            "phone_masked",
            "bucket",
            "total_calls",
            "connected_calls",
            "last_call_at",
            "current_disposition",
            "ever_success"
        ],
        rows
    )


def generate_rejections(connection, output_dir):
    """
    Generate rejections.csv.

    No customer PII is included.
    """

    rejection_records = connection.execute(
        """
        SELECT
            workflow_id,
            batch_id,
            row_number,
            reason

        FROM rejections

        ORDER BY
            workflow_id,
            batch_id,
            row_number
        """
    ).fetchall()

    rows = [
        [
            row["workflow_id"],
            row["batch_id"],
            row["row_number"],
            row["reason"]
        ]
        for row in rejection_records
    ]

    write_csv(
        output_dir / "rejections.csv",
        [
            "workflow_id",
            "batch_id",
            "row_number",
            "reason"
        ],
        rows
    )


def generate_data_quality(connection, output_dir):
    """
    Generate data_quality.json.

    Includes persistent counters and rejection breakdown.
    """

    stats_rows = connection.execute(
        """
        SELECT metric, value
        FROM pipeline_stats
        """
    ).fetchall()

    stats = {
        row["metric"]: row["value"]
        for row in stats_rows
    }

    rejection_rows = connection.execute(
        """
        SELECT reason, COUNT(*) AS total
        FROM rejections
        GROUP BY reason
        ORDER BY reason
        """
    ).fetchall()

    rejections_by_reason = {
        row["reason"]: row["total"]
        for row in rejection_rows
    }

    report = {
        "lead_rows_total": stats.get("lead_rows_total", 0),
        "lead_rows_rejected": stats.get("lead_rows_rejected", 0),
        "rejections_by_reason": rejections_by_reason,
        "duplicate_lead_rows_merged": stats.get(
            "duplicate_lead_rows_merged", 0
        ),
        "field_warnings": stats.get("field_warnings", 0),
        "events_total": stats.get("events_total", 0),
        "malformed_events": stats.get("malformed_events", 0),
        "duplicate_events_dropped": stats.get(
            "duplicate_events_dropped", 0
        ),
        "orphan_events": stats.get("orphan_events", 0),
        "unknown_disposition_events": stats.get(
            "unknown_disposition_events", 0
        )
    }

    with open(
        output_dir / "data_quality.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=2
        )


def generate_reports(output_path):
    """
    Generate all five required Assignment A reports.
    """

    output_dir = Path(output_path)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = get_connection()

    try:

        dispositions = load_dispositions()

        # Load all valid customer records.
        leads = connection.execute(
            """
            SELECT *
            FROM leads
            ORDER BY workflow_id, external_ref
            """
        ).fetchall()

        # Load only events linked to valid leads.
        events = connection.execute(
            """
            SELECT
                e.event_id,
                e.event_type,
                e.workflow_id,
                e.call_id,
                e.occurred_at,
                e.payload_json,
                el.lead_id

            FROM events e

            JOIN event_links el
                ON el.event_id = e.event_id

            WHERE el.lead_id IS NOT NULL

            ORDER BY e.occurred_at
            """
        ).fetchall()

        calls_by_lead = build_calls(
            events,
            dispositions
        )

        generate_batch_summary(
            leads,
            calls_by_lead,
            dispositions,
            output_dir
        )

        generate_daily_overview(
            calls_by_lead,
            dispositions,
            output_dir
        )

        generate_lead_report(
            leads,
            calls_by_lead,
            dispositions,
            output_dir
        )

        generate_rejections(
            connection,
            output_dir
        )

        generate_data_quality(
            connection,
            output_dir
        )

        print("\nAll five reports generated successfully!")

        print("\nOutput directory:", output_dir.resolve())

        print("\nGenerated files:")

        for file_path in sorted(output_dir.iterdir()):

            if file_path.is_file():
                print("-", file_path.name)

    finally:

        connection.close()

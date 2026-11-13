
from reports import (
    get_bucket,
    get_effective_disposition,
    build_calls
)


# Small sample of the official disposition catalogue.
DISPOSITIONS = {
    ("motor_renewal", "renewed"): {
        "is_terminal": True,
        "is_success": True
    },
    ("motor_renewal", "not_interested"): {
        "is_terminal": True,
        "is_success": False
    },
    ("motor_renewal", "payment_link_sent"): {
        "is_terminal": False,
        "is_success": False
    }
}


def make_call(
    disposition=None,
    telephony_failed=False
):
    return {
        "workflow_id": "motor_renewal",
        "effective_disposition": disposition,
        "telephony_failed": telephony_failed
    }


def make_event(
    event_id,
    event_type,
    occurred_at,
    payload=None,
    call_id="call_001"
):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "payload_json": __import__("json").dumps(payload or {}),
        "call_id": call_id,
        "workflow_id": "motor_renewal",
        "lead_id": 1
    }


# TEST 1: Customer with no calls.
def test_yet_to_reach_out():

    result = get_bucket([], DISPOSITIONS)

    assert result == "yet_to_reach_out"


# TEST 2: Any terminal disposition makes the lead completed.
def test_completed_bucket():

    calls = [
        make_call("payment_link_sent"),
        make_call("renewed")
    ]

    result = get_bucket(calls, DISPOSITIONS)

    assert result == "completed"


# TEST 3: All calls failed at telephony layer.
def test_telephony_failed_bucket():

    calls = [
        make_call(telephony_failed=True),
        make_call(telephony_failed=True)
    ]

    result = get_bucket(calls, DISPOSITIONS)

    assert result == "in_progress_telephony_failed"


# TEST 4: Remaining calls belong to dialed bucket.
def test_in_progress_dialed_bucket():

    calls = [
        make_call("payment_link_sent"),
        make_call(telephony_failed=False)
    ]

    result = get_bucket(calls, DISPOSITIONS)

    assert result == "in_progress_dialed"


# TEST 5: Latest supervisor override wins.
def test_supervisor_override_wins():

    events = [
        make_event(
            "evt_1",
            "disposition.set",
            "2026-10-01T10:00:00+05:30",
            {"disposition_code": "renewed"}
        ),
        make_event(
            "evt_2",
            "disposition.override",
            "2026-10-01T11:00:00+05:30",
            {"disposition_code": "not_interested"}
        )
    ]

    result = get_effective_disposition(
        events,
        "motor_renewal",
        DISPOSITIONS
    )

    assert result == "not_interested"


# TEST 6: Latest agent disposition wins when there is no override.
def test_latest_agent_disposition_wins():

    events = [
        make_event(
            "evt_1",
            "disposition.set",
            "2026-10-01T10:00:00+05:30",
            {"disposition_code": "payment_link_sent"}
        ),
        make_event(
            "evt_2",
            "disposition.set",
            "2026-10-01T11:00:00+05:30",
            {"disposition_code": "renewed"}
        )
    ]

    result = get_effective_disposition(
        events,
        "motor_renewal",
        DISPOSITIONS
    )

    assert result == "renewed"


# TEST 7: Unknown disposition must be ignored.
def test_unknown_disposition_ignored():

    events = [
        make_event(
            "evt_1",
            "disposition.set",
            "2026-10-01T10:00:00+05:30",
            {"disposition_code": "unknown_code"}
        )
    ]

    result = get_effective_disposition(
        events,
        "motor_renewal",
        DISPOSITIONS
    )

    assert result is None


# TEST 8: Calls require a linked initiated event.
def test_call_requires_initiated_event():

    events = [
        make_event(
            "evt_1",
            "call.connected",
            "2026-10-01T10:05:00+05:30"
        ),
        make_event(
            "evt_2",
            "call.ended",
            "2026-10-01T10:10:00+05:30"
        )
    ]

    result = build_calls(events, DISPOSITIONS)

    assert result == {}


# TEST 9: Connected call is counted correctly.
def test_connected_call():

    events = [
        make_event(
            "evt_1",
            "call.initiated",
            "2026-10-01T10:00:00+05:30"
        ),
        make_event(
            "evt_2",
            "call.connected",
            "2026-10-01T10:01:00+05:30"
        )
    ]

    result = build_calls(events, DISPOSITIONS)

    calls = result[1]

    assert len(calls) == 1
    assert calls[0]["connected"] is True
    assert calls[0]["telephony_failed"] is False

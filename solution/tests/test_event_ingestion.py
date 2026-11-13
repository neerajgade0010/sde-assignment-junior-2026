
from datetime import datetime

from event_ingestion import (
    normalize_timestamp,
    load_dispositions
)


def test_utc_timestamp():

    result = normalize_timestamp(
        "2026-10-01T05:26:10Z"
    )

    assert result == "2026-10-01T10:56:10+05:30"


def test_offset_timestamp():

    result = normalize_timestamp(
        "2026-10-01T10:40:19+05:30"
    )

    assert result == "2026-10-01T10:40:19+05:30"


def test_naive_timestamp_means_ist():

    result = normalize_timestamp(
        "2026-10-01 09:15:55"
    )

    assert result == "2026-10-01T09:15:55+05:30"


def test_invalid_timestamp():

    try:
        normalize_timestamp("not-a-date")
        assert False, "Expected ValueError"

    except ValueError:
        pass


def test_disposition_catalogue():

    dispositions = load_dispositions()

    renewed = dispositions[
        ("motor_renewal", "renewed")
    ]

    assert renewed["is_terminal"] is True
    assert renewed["is_success"] is True


def test_unknown_workflow_disposition():

    dispositions = load_dispositions()

    assert (
        "motor_renewal",
        "unknown_code"
    ) not in dispositions

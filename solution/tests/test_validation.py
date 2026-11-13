
import pytest

from validation import (
    normalize_header,
    normalize_phone,
    normalize_date,
    normalize_decimal,
    normalize_enum
)


def test_header_normalization():
    assert normalize_header(" Customer_Name ") == "customer name"


def test_valid_phone():
    assert normalize_phone("91-77187-50036") == "+917718750036"


def test_phone_with_zero():
    assert normalize_phone("09876543210") == "+919876543210"


def test_invalid_phone():
    with pytest.raises(ValueError):
        normalize_phone("1234567890")


def test_date_formats():
    assert normalize_date("01-Dec-2026") == "2026-12-01"
    assert normalize_date("01/12/2026") == "2026-12-01"
    assert normalize_date("01-12-2026") == "2026-12-01"
    assert normalize_date("2026-12-01") == "2026-12-01"


def test_invalid_date():
    with pytest.raises(ValueError):
        normalize_date("31/02/2026")


def test_decimal():
    assert normalize_decimal("₹1,27,554") == "127554.00"
    assert normalize_decimal("Rs. 1500") == "1500.00"


def test_invalid_decimal():
    with pytest.raises(ValueError):
        normalize_decimal("-100")


def test_enum():
    assert normalize_enum("HI", ["en", "hi", "ta"]) == "hi"


def test_invalid_enum():
    with pytest.raises(ValueError):
        normalize_enum("HINDI", ["en", "hi", "ta"])

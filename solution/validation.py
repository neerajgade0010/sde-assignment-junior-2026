
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def normalize_header(header):
    """
    Normalise CSV column names.

    Example:
    ' Customer_Name ' -> 'customer name'
    'Customer   Name' -> 'customer name'
    """

    header = header.strip().lower()
    header = re.sub(r"[_\s]+", " ", header)

    return header


def normalize_phone(value):
    """
    Normalise an Indian mobile number.

    Example:
    91-77187-50036 -> +917718750036
    """

    if value is None or not str(value).strip():
        return None

    digits = re.sub(r"\D", "", str(value))

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("invalid_phone")

    return "+91" + digits


def normalize_date(value):
    """
    Accept supported date formats.

    Returns ISO format: YYYY-MM-DD.
    """

    if value is None or not str(value).strip():
        return None

    value = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d-%b-%Y"
    ]

    for date_format in formats:
        try:
            parsed_date = datetime.strptime(value, date_format)
            return parsed_date.strftime("%Y-%m-%d")

        except ValueError:
            continue

    raise ValueError("invalid_date")


def normalize_decimal(value):
    """
    Normalise currency and decimal values.

    Supports Indian and Western comma grouping.

    Examples:
    ₹1,27,554 -> 127554.00
    Rs. 1500 -> 1500.00
    127,554 -> 127554.00
    2500.5 -> 2500.50
    """

    if value is None or not str(value).strip():
        return None

    value = str(value).strip()

    # Remove optional currency prefixes.
    value = re.sub(
        r"^(?:₹|INR|Rs\.?)\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    # Accept plain numbers, Indian grouping and Western grouping.
    pattern = (
        r"(?:"
        r"\d+"
        r"|\d{1,3}(?:,\d{2})*,\d{3}"
        r"|\d{1,3}(?:,\d{3})+"
        r")(?:\.\d+)?"
    )

    if not re.fullmatch(pattern, value):
        raise ValueError("invalid_decimal")

    try:
        amount = Decimal(value.replace(",", ""))

        if amount < 0:
            raise ValueError("invalid_decimal")

        amount = amount.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        return format(amount, ".2f")

    except InvalidOperation:
        raise ValueError("invalid_decimal")


def normalize_enum(value, allowed_values):
    """
    Validate enum values without considering letter case.

    Example:
    HI -> hi
    """

    if value is None or not str(value).strip():
        return None

    value = str(value).strip().casefold()

    allowed = {
        str(item).casefold(): str(item).lower()
        for item in allowed_values
    }

    if value not in allowed:
        raise ValueError("invalid_enum")

    return allowed[value]


def normalize_field_value(field, value):
    """
    Apply normalisation based on the field type
    defined in the workflow schema.
    """

    if value is None or not str(value).strip():
        return None

    field_type = field["type"]

    if field_type == "string":
        return str(value).strip()

    if field_type == "phone":
        return normalize_phone(value)

    if field_type == "date":
        return normalize_date(value)

    if field_type == "decimal":
        return normalize_decimal(value)

    if field_type == "enum":
        return normalize_enum(
            value,
            field.get("values", [])
        )

    raise ValueError(
        f"unsupported_field_type:{field_type}"
    )

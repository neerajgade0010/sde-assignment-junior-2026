
from schema_loader import load_schema, map_headers


def test_load_motor_schema():

    schema = load_schema("motor_renewal")

    assert schema["workflow_id"] == "motor_renewal"

    assert len(schema["fields"]) > 0


def test_load_policy_schema():

    schema = load_schema("policy_feedback")

    assert schema["workflow_id"] == "policy_feedback"


def test_header_alias_mapping():

    schema = load_schema("motor_renewal")

    headers = [
        "Name",
        "Mobile",
        "Policy No",
        "Extra Column"
    ]

    mapping = map_headers(headers, schema)

    assert mapping["customer_name"] == 0
    assert mapping["phone"] == 1
    assert mapping["policy_number"] == 2

    assert "Extra Column" not in mapping


def test_header_normalisation():

    schema = load_schema("motor_renewal")

    headers = [
        " CUSTOMER_NAME ",
        "Phone Number",
        "Policy_Number"
    ]

    mapping = map_headers(headers, schema)

    assert mapping["customer_name"] == 0
    assert mapping["phone"] == 1
    assert mapping["policy_number"] == 2

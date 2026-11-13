
import json
from pathlib import Path

from validation import normalize_header


# Locate the original company-provided schemas.
BASE_DIR = Path(__file__).resolve().parent

SCHEMA_DIR = (
    BASE_DIR.parent
    / "assignment-a-data"
    / "schemas"
)


def load_schema(workflow_id):
    """
    Load the JSON schema for a particular workflow.
    """

    schema_path = SCHEMA_DIR / f"{workflow_id}.json"

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema not found for workflow: {workflow_id}"
        )

    with open(schema_path, "r", encoding="utf-8") as file:
        schema = json.load(file)

    if schema.get("workflow_id") != workflow_id:
        raise ValueError("Workflow ID does not match schema")

    return schema


def map_headers(csv_headers, schema):
    """
    Match CSV headers against schema field names
    and their aliases.

    Returns:
        {
            "customer_name": 0,
            "phone": 1,
            "policy_number": 2
        }

    Unknown columns are ignored.
    """

    header_mapping = {}

    fields = schema["fields"]

    for column_index, header in enumerate(csv_headers):

        normalized_header = normalize_header(header)

        for field in fields:

            field_name = field["name"]

            accepted_names = [
                field_name,
                *field.get("aliases", [])
            ]

            normalized_names = [
                normalize_header(name)
                for name in accepted_names
            ]

            if normalized_header in normalized_names:

                # First matching column wins if a field
                # appears more than once in the CSV.
                if field_name not in header_mapping:
                    header_mapping[field_name] = column_index

                break

    return header_mapping

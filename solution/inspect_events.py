
import json
from pathlib import Path
from collections import Counter


EVENTS_DIR = Path("../data/drop_1/events")

event_files = sorted(EVENTS_DIR.glob("*.jsonl"))

event_types = Counter()
event_ids = set()

total_lines = 0
empty_lines = 0
malformed_lines = 0
missing_ids = 0
duplicate_ids = 0

for file_path in event_files:

    print(f"\nInspecting: {file_path.name}")

    with open(file_path, "r", encoding="utf-8") as file:

        for line in file:

            if not line.strip():
                empty_lines += 1
                continue

            total_lines += 1

            try:
                event = json.loads(line)

            except json.JSONDecodeError:
                malformed_lines += 1
                continue

            if not isinstance(event, dict):
                malformed_lines += 1
                continue

            event_id = event.get("event_id")

            if not event_id:
                missing_ids += 1
                continue

            if event_id in event_ids:
                duplicate_ids += 1
            else:
                event_ids.add(event_id)

            event_types[event.get("event_type", "UNKNOWN")] += 1


print("\n========== EVENT STATISTICS ==========")

print("Total non-empty lines:", total_lines)
print("Empty lines:", empty_lines)
print("Malformed JSON:", malformed_lines)
print("Missing event IDs:", missing_ids)
print("Duplicate event IDs:", duplicate_ids)

print("\nEvent type distribution:")

for event_type, count in sorted(event_types.items()):
    print(f"{event_type}: {count}")

print("\nUnique event IDs:", len(event_ids))

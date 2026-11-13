
from database import get_connection

connection = get_connection()

try:

    print("\n========== LINK VERIFICATION ==========\n")

    # Actual successful and unsuccessful links.
    rows = connection.execute(
        """
        SELECT
            link_method,
            CASE
                WHEN lead_id IS NULL THEN 'unlinked'
                ELSE 'linked'
            END AS status,
            COUNT(*) AS total
        FROM event_links
        GROUP BY link_method, status
        ORDER BY link_method, status
        """
    ).fetchall()

    print("Linking method and actual status:")

    for row in rows:
        print(
            f"{row['link_method']} - "
            f"{row['status']}: {row['total']}"
        )

    # Inspect supervisor overrides that remain unlinked.
    print("\nUnlinked supervisor overrides:")

    overrides = connection.execute(
        """
        SELECT
            e.event_id,
            e.workflow_id,
            e.call_id,
            e.occurred_at
        FROM events e
        JOIN event_links el
            ON el.event_id = e.event_id
        WHERE e.event_type = 'disposition.override'
          AND el.lead_id IS NULL
        """
    ).fetchall()

    for event in overrides:
        print(dict(event))

    print("\nTotal unlinked overrides:", len(overrides))

    # Final orphan count.
    orphan_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM event_links
        WHERE lead_id IS NULL
        """
    ).fetchone()[0]

    print("Total orphan events:", orphan_count)

finally:
    connection.close()


from database import get_connection

connection = get_connection()

try:

    print("\n========== EVENT DATABASE VERIFICATION ==========\n")

    # Total events stored.
    total = connection.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]

    print("Total events stored:", total)

    # Event type distribution.
    print("\nEvent type distribution:")

    event_types = connection.execute(
        """
        SELECT event_type, COUNT(*) AS total
        FROM events
        GROUP BY event_type
        ORDER BY event_type
        """
    ).fetchall()

    for row in event_types:
        print(f"{row['event_type']}: {row['total']}")

    # Linked versus orphan events.
    print("\nEvent linking statistics:")

    linking = connection.execute(
        """
        SELECT
            CASE
                WHEN lead_id IS NULL THEN 'orphan'
                ELSE 'linked'
            END AS status,
            COUNT(*) AS total
        FROM event_links
        GROUP BY status
        """
    ).fetchall()

    for row in linking:
        print(f"{row['status']}: {row['total']}")

    # Linking method distribution.
    print("\nLinking methods:")

    methods = connection.execute(
        """
        SELECT link_method, COUNT(*) AS total
        FROM event_links
        GROUP BY link_method
        """
    ).fetchall()

    for row in methods:
        print(f"{row['link_method']}: {row['total']}")

    # Supervisor override verification.
    overrides = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(
                CASE WHEN el.lead_id IS NOT NULL
                THEN 1 ELSE 0 END
            ) AS linked
        FROM events e
        JOIN event_links el
            ON e.event_id = el.event_id
        WHERE e.event_type = 'disposition.override'
        """
    ).fetchone()

    print("\nSupervisor overrides:")
    print("Total:", overrides["total"])
    print("Linked:", overrides["linked"])

    # Persistent pipeline counters.
    print("\nData quality counters:")

    stats = connection.execute(
        """
        SELECT metric, value
        FROM pipeline_stats
        ORDER BY metric
        """
    ).fetchall()

    for row in stats:
        print(f"{row['metric']}: {row['value']}")

finally:
    connection.close()

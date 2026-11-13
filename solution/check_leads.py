
from database import get_connection
from security import decrypt_value


connection = get_connection()

try:
    # Count stored customers.
    result = connection.execute(
        "SELECT COUNT(*) AS total FROM leads"
    ).fetchone()

    print("Total stored leads:", result["total"])

    # Retrieve one customer without printing their details.
    lead = connection.execute(
        """
        SELECT
            phone_encrypted,
            customer_name_encrypted,
            phone_hash
        FROM leads
        LIMIT 1
        """
    ).fetchone()

    if lead:

        print(
            "Phone stored as encrypted data:",
            isinstance(lead["phone_encrypted"], bytes)
        )

        print(
            "Name stored as encrypted data:",
            isinstance(lead["customer_name_encrypted"], bytes)
        )

        print(
            "Phone fingerprint exists:",
            bool(lead["phone_hash"])
        )

        # Verify that decryption works.
        phone = decrypt_value(lead["phone_encrypted"])
        name = decrypt_value(lead["customer_name_encrypted"])

        print("Phone decryption successful:", bool(phone))
        print("Name decryption successful:", bool(name))

    # Display data-quality counters.
    print("\nData quality counters:")

    stats = connection.execute(
        "SELECT metric, value FROM pipeline_stats ORDER BY metric"
    ).fetchall()

    for stat in stats:
        print(f"{stat['metric']}: {stat['value']}")

finally:
    connection.close()

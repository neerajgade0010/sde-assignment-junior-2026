
import sqlite3

# Connect to our database
connection = sqlite3.connect("pipeline.db")

# Get all table names
cursor = connection.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    AND name NOT LIKE 'sqlite_%'
""")

# Display the tables
print("Tables in our database:")

for row in cursor:
    print(row[0])

# Close the connection
connection.close()


import sqlite3
from pathlib import Path


# Database location
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "pipeline.db"


# Counters required by Assignment A
INITIAL_STATS = [
    "lead_rows_total",
    "lead_rows_rejected",
    "duplicate_lead_rows_merged",
    "field_warnings",
    "events_total",
    "malformed_events",
    "duplicate_events_dropped",
    "orphan_events",
    "unknown_disposition_events",
]


def get_connection():
    """
    Create a connection to the SQLite database.
    """

    connection = sqlite3.connect(DATABASE_PATH)

    connection.execute("PRAGMA foreign_keys = ON")

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    """
    Create all tables, indexes and initial statistics.
    """

    connection = get_connection()

    try:

        connection.executescript("""

            CREATE TABLE IF NOT EXISTS leads (

                lead_id INTEGER PRIMARY KEY AUTOINCREMENT,

                workflow_id TEXT NOT NULL,

                external_ref TEXT NOT NULL,

                batch_id TEXT NOT NULL,

                phone_hash TEXT NOT NULL,

                phone_encrypted BLOB NOT NULL,

                customer_name_encrypted BLOB NOT NULL,

                fields_json TEXT NOT NULL DEFAULT '{}',

                created_at TEXT NOT NULL,

                updated_at TEXT NOT NULL,

                UNIQUE (workflow_id, phone_hash)
            );


            CREATE TABLE IF NOT EXISTS events (

                event_id TEXT PRIMARY KEY,

                event_type TEXT NOT NULL,

                workflow_id TEXT NOT NULL,

                call_id TEXT,

                occurred_at TEXT NOT NULL,

                phone_hash TEXT,

                phone_encrypted BLOB,

                payload_json TEXT NOT NULL,

                received_drop TEXT NOT NULL,

                created_at TEXT NOT NULL
            );


            CREATE TABLE IF NOT EXISTS event_links (

                event_id TEXT PRIMARY KEY,

                lead_id INTEGER,

                link_method TEXT,

                updated_at TEXT NOT NULL,

                FOREIGN KEY (event_id)
                    REFERENCES events(event_id),

                FOREIGN KEY (lead_id)
                    REFERENCES leads(lead_id)
            );


            CREATE TABLE IF NOT EXISTS rejections (

                rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,

                workflow_id TEXT NOT NULL,

                batch_id TEXT NOT NULL,

                row_number INTEGER NOT NULL,

                reason TEXT NOT NULL
            );


            CREATE TABLE IF NOT EXISTS ingested_files (

                file_id INTEGER PRIMARY KEY AUTOINCREMENT,

                drop_name TEXT NOT NULL,

                relative_path TEXT NOT NULL,

                file_hash TEXT NOT NULL,

                file_type TEXT NOT NULL,

                processed_at TEXT NOT NULL,

                UNIQUE (drop_name, relative_path)
            );


            CREATE TABLE IF NOT EXISTS pipeline_stats (

                metric TEXT PRIMARY KEY,

                value INTEGER NOT NULL DEFAULT 0
            );


            CREATE INDEX IF NOT EXISTS idx_leads_workflow
                ON leads(workflow_id);


            CREATE INDEX IF NOT EXISTS idx_events_call
                ON events(workflow_id, call_id);


            CREATE INDEX IF NOT EXISTS idx_events_phone
                ON events(workflow_id, phone_hash);


            CREATE INDEX IF NOT EXISTS idx_event_links_lead
                ON event_links(lead_id);


            CREATE TRIGGER IF NOT EXISTS prevent_event_update

            BEFORE UPDATE ON events

            BEGIN

                SELECT RAISE(
                    ABORT,
                    'Interaction ledger events cannot be updated'
                );

            END;


            CREATE TRIGGER IF NOT EXISTS prevent_event_delete

            BEFORE DELETE ON events

            BEGIN

                SELECT RAISE(
                    ABORT,
                    'Interaction ledger events cannot be deleted'
                );

            END;

        """)


        # Initialise counters without resetting existing values.
        for metric in INITIAL_STATS:

            connection.execute(
                """
                INSERT OR IGNORE INTO pipeline_stats (metric, value)
                VALUES (?, 0)
                """,
                (metric,)
            )


        connection.commit()

        print("Database initialized successfully!")

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


if __name__ == "__main__":

    initialize_database()

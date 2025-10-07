# This script migrates data from a local SQLite database to Google Cloud Firestore.
#
# Prerequisites:
# 1. A Google Cloud project with Firestore enabled.
# 2. The `google-cloud-firestore` Python library installed.
#    pip install google-cloud-firestore
# 3. Authentication set up for Google Cloud.
#    - Run `gcloud auth application-default login` in your terminal.
#    - Or, set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to your service account key file.
#
# How to run:
# 1. Replace 'YOUR_PROJECT_ID' with your actual Google Cloud project ID.
# 2. Make sure the `SQLITE_DB_PATH` is correct.
# 3. Run the script from your terminal: `python sqlite_to_firestore.py`

import sqlite3
from google.cloud import firestore

# --- Configuration ---
# Replace with your Google Cloud project ID
PROJECT_ID = "my-gen-cli-ultrenz"
# Path to your SQLite database file
SQLITE_DB_PATH = "db/analytics.db"

# --- 1. Initialize Firestore Client ---
# This will use your default project and credentials.
# Make sure you have authenticated with `gcloud auth application-default login`
# or have set the GOOGLE_APPLICATION_CREDENTIALS environment variable.
try:
    db = firestore.Client(project=PROJECT_ID)
    print(f"Successfully connected to Firestore project: {PROJECT_ID}")
except Exception as e:
    print(f"Error connecting to Firestore: {e}")
    print("Please make sure you have authenticated correctly and the project ID is correct.")
    exit()

# --- 2. Function to get all table names from SQLite ---
def get_sqlite_tables(conn):
    """Returns a list of table names in the SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table[0] for table in cursor.fetchall()]
    return tables

# --- 3. Function to read data from a SQLite table ---
def read_from_table(conn, table_name):
    """Reads all rows from a table and returns them as a list of dictionaries."""
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

# --- 4. Main Migration Logic ---
def migrate_to_firestore():
    """Connects to SQLite, reads data, and writes it to Firestore."""
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(SQLITE_DB_PATH)
        print(f"Successfully connected to SQLite database: {SQLITE_DB_PATH}")

        tables = get_sqlite_tables(conn)
        print(f"Found tables: {', '.join(tables)}")

        for table_name in tables:
            print(f"--- Migrating table: {table_name} ---")
            
            # Read data from the SQLite table
            data = read_from_table(conn, table_name)
            
            if not data:
                print(f"Table '{table_name}' is empty. Skipping.")
                continue

            # Get a reference to the Firestore collection
            collection_ref = db.collection(table_name)

            # Write data to Firestore in a batch
            batch = db.batch()
            count = 0
            for item in data:
                # Create a new document reference with an auto-generated ID
                doc_ref = collection_ref.document()
                batch.set(doc_ref, item)
                count += 1
                # Firestore batches have a limit of 500 operations.
                if count % 500 == 0:
                    print(f"Committing batch of {count} documents to '{table_name}'...")
                    batch.commit()
                    batch = db.batch() # Start a new batch
            
            # Commit any remaining documents in the last batch
            if count % 500 != 0:
                print(f"Committing final batch of {count % 500} documents to '{table_name}'...")
                batch.commit()

            print(f"Successfully migrated {len(data)} documents to collection '{table_name}'.")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("SQLite connection closed.")

# --- 5. Run the Migration ---
if __name__ == "__main__":
    print("Starting SQLite to Firestore migration...")
    migrate_to_firestore()
    print("Migration process complete.")

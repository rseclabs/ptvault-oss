"""Migration 027: Purple-team outcomes on test executions

Adds two columns to test_executions:

  - outcome:     highest detection level the defenders reached, one of
                 'prevented' > 'alerted' > 'logged' > 'not_detected'.
                 NULL means not evaluated yet.
  - detected_by: free text naming the control/source (EDR, SIEM rule, ...)

Existing rows stay NULL (not evaluated).

Created: 2026-10-31
"""


def upgrade(db):
    cursor = db.cursor()
    cursor.execute("PRAGMA table_info(test_executions)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'outcome' not in columns:
        print("  -> Adding outcome to test_executions")
        cursor.execute("ALTER TABLE test_executions ADD COLUMN outcome TEXT")
    if 'detected_by' not in columns:
        print("  -> Adding detected_by to test_executions")
        cursor.execute("ALTER TABLE test_executions ADD COLUMN detected_by TEXT")

    db.commit()
    print("  -> Execution outcomes migration completed")


def downgrade(db):
    # SQLite cannot drop columns; clear the values instead
    cursor = db.cursor()
    cursor.execute("UPDATE test_executions SET outcome = NULL, detected_by = NULL")
    db.commit()

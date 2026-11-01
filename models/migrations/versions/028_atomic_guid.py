"""Migration 028: Stable identity for Atomic Red Team tests

Re-downloading the Atomics library used to DELETE every row and re-insert
it, so every atomic got a new id and every test_plan_items.atomic_id
pointed at nothing (foreign keys are not enforced). The importer now
updates rows in place, matching on Atomic Red Team's per-test
auto_generated_guid. This adds the column it matches on.

Existing rows get their GUID filled in on the next library download
(matched by technique + test position, which is what they were keyed on).

Created: 2026-10-31
"""


def upgrade(db):
    cursor = db.cursor()
    cursor.execute("PRAGMA table_info(atomics)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'atomic_guid' not in columns:
        print("  -> Adding atomic_guid to atomics")
        cursor.execute("ALTER TABLE atomics ADD COLUMN atomic_guid TEXT")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_atomics_guid "
        "ON atomics(atomic_guid) WHERE atomic_guid IS NOT NULL"
    )

    db.commit()
    print("  -> Atomic GUID migration completed")


def downgrade(db):
    cursor = db.cursor()
    cursor.execute("DROP INDEX IF EXISTS idx_atomics_guid")
    cursor.execute("UPDATE atomics SET atomic_guid = NULL")
    db.commit()

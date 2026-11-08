"""
Migration 032: Record who created shared content

Adds created_by to writeups, commands, test_plans and navigator_layers so
shared content can be changed only by its creator or an admin. Existing rows
keep created_by NULL: their creator is unknown, so only admins may change
them.

Created: 2026-11-07
"""

TABLES = ('writeups', 'commands', 'test_plans', 'navigator_layers')


def upgrade(db):
    cursor = db.cursor()
    for table in TABLES:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,))
        if cursor.fetchone() is None:
            continue
        cursor.execute(f"SELECT COUNT(*) FROM pragma_table_info('{table}') WHERE name = 'created_by'")
        if cursor.fetchone()[0] == 0:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN created_by INTEGER')
    db.commit()
    print("  ✓ Shared content records its creator")


def downgrade(db):
    # SQLite cannot drop columns on older versions; the column is harmless.
    pass

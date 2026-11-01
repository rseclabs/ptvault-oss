"""
Migration 003: Add Host Indicators

Adds visual indicator columns to hosts table:
- rooted: Root/admin access obtained
- shell: Shell access obtained
- interested: Worth investigating
- not_interested: Nothing interesting
- out_of_scope: Do not test
- flagged: Needs review
- reviewed: Testing completed
- color_category: Color-based grouping

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Check which indicator columns already exist
    cursor.execute("SELECT name FROM pragma_table_info('hosts')")
    existing_columns = {row[0] for row in cursor.fetchall()}

    indicator_columns = {
        'rooted': 'INTEGER DEFAULT 0',
        'shell': 'INTEGER DEFAULT 0',
        'interested': 'INTEGER DEFAULT 0',
        'not_interested': 'INTEGER DEFAULT 0',
        'out_of_scope': 'INTEGER DEFAULT 0',
        'flagged': 'INTEGER DEFAULT 0',
        'reviewed': 'INTEGER DEFAULT 0',
        'color_category': 'TEXT DEFAULT NULL'
    }

    # Add missing columns
    columns_added = 0
    for col_name, col_type in indicator_columns.items():
        if col_name not in existing_columns:
            cursor.execute(f'ALTER TABLE hosts ADD COLUMN {col_name} {col_type}')
            columns_added += 1

    db.commit()

    if columns_added > 0:
        print(f"  ✓ Added {columns_added} indicator column(s) to hosts table")
    else:
        print("  ✓ All indicator columns already exist")


def downgrade(db):
    """
    Rollback not supported for ALTER TABLE ADD COLUMN in SQLite.

    SQLite does not support dropping columns in older versions.
    To fully rollback, the hosts table would need to be recreated.
    """
    print("  ! Cannot drop columns in SQLite - manual intervention required")
    raise NotImplementedError("SQLite does not support DROP COLUMN")

"""
Migration 033: Flag test plan items for re-review after an Atomics refresh

Adds test_plan_items.needs_review. Refreshing the Atomic Red Team library
sets it on items whose test's command, cleanup, inputs, dependencies or
elevation changed; script generation refuses until the items are marked
reviewed (M-6). Existing items start at 0.

Created: 2026-11-07
"""


def upgrade(db):
    cursor = db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = 'test_plan_items'")
    if cursor.fetchone() is not None:
        cursor.execute("SELECT COUNT(*) FROM pragma_table_info('test_plan_items') WHERE name = 'needs_review'")
        if cursor.fetchone()[0] == 0:
            cursor.execute('ALTER TABLE test_plan_items ADD COLUMN needs_review INTEGER NOT NULL DEFAULT 0')
    db.commit()
    print("  ✓ Test plan items can be flagged for re-review")


def downgrade(db):
    # SQLite cannot drop columns on older versions; the column is harmless.
    pass

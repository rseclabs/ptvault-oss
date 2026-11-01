"""Migration 024: Hierarchical notes

Promotes the flat `engagement_notes` and `host_notes` lists into trees.
Both tables gain:
- parent_id INTEGER REFERENCES <same table>(id) ON DELETE RESTRICT
- sort_order INTEGER NOT NULL DEFAULT 0

Existing rows stay as roots (parent_id NULL) and are assigned a stable
sort_order based on creation time so the existing order is preserved.

The route layer enforces "block delete on children" with a 409 response
(mirroring the Clients delete pattern) before SQLite's ON DELETE RESTRICT
ever fires.

Created: 2026-05-04
"""


def _add_columns_and_index(cursor, table):
    """Add parent_id + sort_order to a notes table if not already present."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]

    if 'parent_id' not in columns:
        print(f"  -> Adding parent_id column to {table}")
        cursor.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN parent_id INTEGER REFERENCES {table}(id) ON DELETE RESTRICT"
        )

    if 'sort_order' not in columns:
        print(f"  -> Adding sort_order column to {table}")
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
        )

    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{table}_parent "
        f"ON {table}(parent_id, sort_order)"
    )


def _backfill_sort_order(cursor, table, scope_column):
    """Assign a stable sort_order to existing rows by created_at within scope.

    Only touches rows where sort_order is currently 0 (i.e. the default
    we just added) to keep the migration idempotent.
    """
    print(f"  -> Backfilling sort_order on {table}")
    # CTE ranks each note within its scope by created_at, then we copy
    # the rank back into sort_order. SQLite 3.25+ supports ROW_NUMBER —
    # PTVault requires 3.31+ so this is safe.
    cursor.execute(f"""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY {scope_column}
                       ORDER BY created_at, id
                   ) AS rn
            FROM {table}
        )
        UPDATE {table}
           SET sort_order = (SELECT rn FROM ranked WHERE ranked.id = {table}.id)
         WHERE sort_order = 0
    """)


def upgrade(db):
    cursor = db.cursor()

    _add_columns_and_index(cursor, 'engagement_notes')
    _add_columns_and_index(cursor, 'host_notes')

    _backfill_sort_order(cursor, 'engagement_notes', 'engagement_id')
    _backfill_sort_order(cursor, 'host_notes', 'host_id')

    print("  -> Hierarchical notes migration completed")


def downgrade(db):
    cursor = db.cursor()
    # SQLite cannot drop a column on older versions; null parent_id and
    # reset sort_order so the columns are effectively neutralized.
    cursor.execute("DROP INDEX IF EXISTS idx_engagement_notes_parent")
    cursor.execute("DROP INDEX IF EXISTS idx_host_notes_parent")
    cursor.execute("UPDATE engagement_notes SET parent_id = NULL, sort_order = 0")
    cursor.execute("UPDATE host_notes SET parent_id = NULL, sort_order = 0")

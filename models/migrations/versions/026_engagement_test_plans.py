"""Migration 026: Per-engagement test plans

Test plans used to be global: every engagement saw and edited the same
plans. This adds `test_plans.engagement_id`:

  - engagement_id IS NULL      -> reusable template (shared library)
  - engagement_id = <id>       -> plan owned by that engagement

All existing plans become templates (their engagement_id stays NULL).

Executions point at plans with ON DELETE CASCADE, so leaving historical
executions on a template would mean deleting the template wipes those
engagements' results. For every (engagement, template) pair that already
has executions, the template is copied into that engagement (items too)
and the executions are re-pointed at the copy and its items.

`source_template_id` records which template an engagement plan came from.

Created: 2026-10-31
"""


def _columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def upgrade(db):
    cursor = db.cursor()
    cols = _columns(cursor, 'test_plans')

    if 'engagement_id' not in cols:
        print("  -> Adding engagement_id to test_plans")
        cursor.execute(
            "ALTER TABLE test_plans ADD COLUMN engagement_id INTEGER "
            "REFERENCES engagements(id) ON DELETE CASCADE"
        )
    if 'source_template_id' not in cols:
        print("  -> Adding source_template_id to test_plans")
        cursor.execute(
            "ALTER TABLE test_plans ADD COLUMN source_template_id INTEGER "
            "REFERENCES test_plans(id) ON DELETE SET NULL"
        )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_plans_engagement "
        "ON test_plans(engagement_id)"
    )

    # Give each engagement its own copy of any template it has executed.
    cursor.execute("""
        SELECT DISTINCT te.engagement_id, te.test_plan_id
        FROM test_executions te
        JOIN test_plans tp ON tp.id = te.test_plan_id
        WHERE tp.engagement_id IS NULL
        ORDER BY te.engagement_id, te.test_plan_id
    """)
    pairs = cursor.fetchall()
    if pairs:
        print(f"  -> Copying {len(pairs)} executed template(s) into their engagements")

    for engagement_id, template_id in pairs:
        cursor.execute("""
            INSERT INTO test_plans (name, description, target_platform, tags,
                                    engagement_id, source_template_id,
                                    created_at, updated_at)
            SELECT name, description, target_platform, tags, ?, id,
                   created_at, updated_at
            FROM test_plans WHERE id = ?
        """, (engagement_id, template_id))
        new_plan_id = cursor.lastrowid

        cursor.execute("""
            SELECT id, atomic_id, custom_name, custom_command, custom_platform,
                   sort_order, enabled, input_overrides, notes, created_at
            FROM test_plan_items WHERE test_plan_id = ? ORDER BY id
        """, (template_id,))
        item_map = {}
        for row in cursor.fetchall():
            cursor.execute("""
                INSERT INTO test_plan_items (test_plan_id, atomic_id, custom_name,
                    custom_command, custom_platform, sort_order, enabled,
                    input_overrides, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_plan_id, *row[1:]))
            item_map[row[0]] = cursor.lastrowid

        for old_item_id, new_item_id in item_map.items():
            cursor.execute("""
                UPDATE test_executions
                SET test_plan_id = ?, test_plan_item_id = ?
                WHERE engagement_id = ? AND test_plan_id = ? AND test_plan_item_id = ?
            """, (new_plan_id, new_item_id, engagement_id, template_id, old_item_id))

    db.commit()
    print("  -> Per-engagement test plans migration completed")


def downgrade(db):
    # SQLite cannot drop columns; collapse everything back to global plans.
    cursor = db.cursor()
    cursor.execute("UPDATE test_plans SET engagement_id = NULL, source_template_id = NULL")
    db.commit()

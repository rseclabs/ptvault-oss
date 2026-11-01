"""Migration 022: Add template_id to reports

TemplateDAO.apply_to_engagement creates a row in `reports`, but never
recorded which template produced it. TemplateDAO.get_with_usage_count
was joining `report_sections` (a table no longer used by this flow),
so usage_count was always 0 and the API surfaced misleading data.

This migration:
- Adds reports.template_id (nullable; preserves existing reports)
- Adds an index for the join
- Backfill is impossible — pre-migration reports lose their template
  association, and that's acceptable since usage_count was always 0
  for them anyway.

Created: 2026-05-03
"""


def upgrade(db):
    cursor = db.cursor()

    # Skip if column already present (re-runs in long-lived dev DBs)
    cursor.execute("PRAGMA table_info(reports)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'template_id' not in columns:
        print("  -> Adding template_id column to reports")
        cursor.execute('''
            ALTER TABLE reports
            ADD COLUMN template_id INTEGER REFERENCES report_templates(id) ON DELETE SET NULL
        ''')

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_template_id ON reports(template_id)"
    )
    print("  -> reports.template_id ready")


def downgrade(db):
    cursor = db.cursor()
    cursor.execute("DROP INDEX IF EXISTS idx_reports_template_id")
    # SQLite cannot drop a column on older versions; leave the column in
    # place. Setting all values to NULL is a no-op for downgrade purposes.
    cursor.execute("UPDATE reports SET template_id = NULL")

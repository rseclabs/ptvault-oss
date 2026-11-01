"""
Migration 008: Add Saved Filters Table

Adds saved_filters table for engagement-specific saved search filters.

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Migration: Add saved_filters table (engagement-specific saved search filters)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            filter_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_saved_filters_engagement ON saved_filters(engagement_id)')

    db.commit()
    print("  ✓ Saved filters table created")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    cursor.execute('DROP INDEX IF EXISTS idx_saved_filters_engagement')
    cursor.execute('DROP TABLE IF EXISTS saved_filters')

    db.commit()
    print("  ✓ Saved filters table removed")

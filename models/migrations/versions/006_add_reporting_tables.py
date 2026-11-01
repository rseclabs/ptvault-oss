"""
Migration 006: Add Reporting Tables

Adds tables for vulnerability writeups and report generation:
- writeups: Reusable vulnerability templates
- reports: Saved report structures per engagement

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Migration: Add writeups table (global, not engagement-specific)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS writeups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            criticality TEXT DEFAULT 'medium',
            cvss_score REAL,
            description TEXT,
            remediation TEXT,
            tags TEXT,
            writeup_type TEXT DEFAULT 'finding',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_writeups_category ON writeups(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_writeups_criticality ON writeups(criticality)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_writeups_type ON writeups(writeup_type)')

    # Migration: Add reports table (engagement-specific report builder)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            structure TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_engagement ON reports(engagement_id)')

    db.commit()
    print("  ✓ Reporting tables created")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    # Drop indexes
    cursor.execute('DROP INDEX IF EXISTS idx_reports_engagement')
    cursor.execute('DROP INDEX IF EXISTS idx_writeups_type')
    cursor.execute('DROP INDEX IF EXISTS idx_writeups_criticality')
    cursor.execute('DROP INDEX IF EXISTS idx_writeups_category')

    # Drop tables
    cursor.execute('DROP TABLE IF EXISTS reports')
    cursor.execute('DROP TABLE IF EXISTS writeups')

    db.commit()
    print("  ✓ Reporting tables removed")

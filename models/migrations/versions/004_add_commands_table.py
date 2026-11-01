"""
Migration 004: Add Commands Table

Adds commands table for custom command database feature.

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Migration: Add commands table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            description TEXT,
            variables TEXT,
            is_custom INTEGER DEFAULT 1,
            is_favorite INTEGER DEFAULT 0,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_commands_category ON commands(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_commands_is_custom ON commands(is_custom)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_commands_is_favorite ON commands(is_favorite)')

    db.commit()
    print("  ✓ Commands table created")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    cursor.execute('DROP INDEX IF EXISTS idx_commands_is_favorite')
    cursor.execute('DROP INDEX IF EXISTS idx_commands_is_custom')
    cursor.execute('DROP INDEX IF EXISTS idx_commands_category')
    cursor.execute('DROP TABLE IF EXISTS commands')

    db.commit()
    print("  ✓ Commands table removed")

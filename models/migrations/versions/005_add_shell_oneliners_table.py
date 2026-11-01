"""
Migration 005: Add Shell One-Liners Table

Adds shell_oneliners table for built-in shell one-liners library.

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Migration: Add shell_oneliners table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shell_oneliners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            subcategory TEXT,
            name TEXT NOT NULL,
            command TEXT NOT NULL,
            description TEXT,
            variables TEXT,
            is_admin INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_shell_oneliners_category ON shell_oneliners(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_shell_oneliners_subcategory ON shell_oneliners(subcategory)')

    db.commit()
    print("  ✓ Shell one-liners table created")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    cursor.execute('DROP INDEX IF EXISTS idx_shell_oneliners_subcategory')
    cursor.execute('DROP INDEX IF EXISTS idx_shell_oneliners_category')
    cursor.execute('DROP TABLE IF EXISTS shell_oneliners')

    db.commit()
    print("  ✓ Shell one-liners table removed")

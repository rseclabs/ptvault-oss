"""
Migration 020: Settings table

Adds a key-value settings table for storing application configuration
such as license keys, preferences, and other admin-controlled values.

Created: 2026-02-24
"""


def upgrade(db):
    """Apply settings table migration."""
    cursor = db.cursor()

    print("  -> Creating settings table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.commit()
    print("  -> Settings table migration completed")


def downgrade(db):
    """Rollback settings table migration."""
    cursor = db.cursor()
    cursor.execute("DROP TABLE IF EXISTS settings")
    db.commit()

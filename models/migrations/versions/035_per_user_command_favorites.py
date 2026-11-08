"""
Migration 035: command favorites per user (L-22)

commands.is_favorite was one flag on the shared row, so any tester could star
or unstar commands for everyone. Favorites move to command_favorites(user_id,
command_id). Each existing flag goes to the command's creator; built-in and
older commands have no recorded creator, so their flags go to every admin.
The old column stays (SQLite cannot always drop it) but is cleared and unused.

Created: 2026-11-08
"""


def upgrade(db):
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS command_favorites (
            user_id INTEGER NOT NULL REFERENCES users(id),
            command_id INTEGER NOT NULL REFERENCES commands(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, command_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_command_favorites_command ON command_favorites(command_id)')
    columns = {row[1] for row in cursor.execute('PRAGMA table_info(commands)')}
    if 'is_favorite' in columns:
        cursor.execute('''
            INSERT OR IGNORE INTO command_favorites (user_id, command_id)
            SELECT c.created_by, c.id FROM commands c
            WHERE c.is_favorite = 1 AND c.created_by IN (SELECT id FROM users)
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO command_favorites (user_id, command_id)
            SELECT u.id, c.id FROM commands c, users u
            WHERE c.is_favorite = 1 AND u.role = 'admin'
              AND (c.created_by IS NULL OR c.created_by NOT IN (SELECT id FROM users))
        ''')
        cursor.execute('UPDATE commands SET is_favorite = 0 WHERE is_favorite != 0')
    db.commit()
    print("  ✓ Command favorites are per user")


def downgrade(db):
    cursor = db.cursor()
    cursor.execute('DROP TABLE IF EXISTS command_favorites')
    db.commit()

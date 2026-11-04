"""
Migration 031: Mark built-in shell one-liners

Adds shell_oneliners.is_builtin. Until now built-ins and user-added one-liners
were both stored with is_admin = 1, so a deleted built-in was never restored
and the API could not protect them.

An existing row is marked built-in only when its category, name and command
all match the shipped list; a built-in someone edited stays as their own
one-liner, and the seed adds a fresh built-in beside it.

Created: 2026-11-03
"""


def upgrade(db):
    cursor = db.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='shell_oneliners'"
    )
    if cursor.fetchone() is None:
        return

    cursor.execute("SELECT COUNT(*) FROM pragma_table_info('shell_oneliners') WHERE name = 'is_builtin'")
    if cursor.fetchone()[0] == 0:
        cursor.execute('ALTER TABLE shell_oneliners ADD COLUMN is_builtin INTEGER NOT NULL DEFAULT 0')

    from models.seed_shell_oneliners import BUILTIN_SHELL_ONELINERS

    for item in BUILTIN_SHELL_ONELINERS:
        cursor.execute(
            'UPDATE shell_oneliners SET is_builtin = 1 WHERE id = ('
            '  SELECT MIN(id) FROM shell_oneliners'
            '  WHERE category = ? AND name = ? AND command = ?)',
            (item['category'], item['name'], item['command'])
        )

    db.commit()
    print("  ✓ Built-in shell one-liners marked")


def downgrade(db):
    cursor = db.cursor()
    cursor.execute('ALTER TABLE shell_oneliners DROP COLUMN is_builtin')
    db.commit()

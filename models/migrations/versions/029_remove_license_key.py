"""Migration 029: Remove stored license key

PTVault is now open source and no longer has a Pro tier, so the
license_key row in settings is unused. Drop it so old keys don't
linger in existing databases.

Created: 2026-11-01
"""


def upgrade(db):
    cursor = db.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
    )
    if cursor.fetchone():
        cursor.execute("DELETE FROM settings WHERE key = 'license_key'")
    db.commit()
    print("  -> Removed stored license key")


def downgrade(db):
    # The deleted key cannot be restored; nothing to undo.
    pass

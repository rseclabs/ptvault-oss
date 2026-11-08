"""
Migration 034: never reuse engagement or evidence IDs; remove what deletes left behind (M-13)

engagements and evidence were declared "id INTEGER PRIMARY KEY", so SQLite
gave a new row max(id)+1: deleting the newest engagement freed its ID, and the
next engagement took it, together with every row the incomplete delete had left
(members, reports, attack maps, plans...). Evidence IDs were reused the same way.

- Both tables are rebuilt with AUTOINCREMENT (SQLite's table-rebuild procedure:
  copy the stored columns, drop, rename, recreate indexes and triggers; the
  evidence generated columns and full-text triggers come back unchanged).
- Their sequences start above every ID still referenced anywhere, so even IDs of
  rows deleted before this migration are not handed out again.
- Rows that belong to engagements (or parent rows) that no longer exist are
  deleted (models/engagement_cleanup.purge_orphans); audit_log is kept.

FOREIGN_KEYS_OFF: the manager turns foreign keys off around this migration
(they are off in PTVault databases anyway; tests turn them on), because a DROP
with them on fires ON DELETE CASCADE (L-32). Helpers: models/migrations/rebuild.py.

Created: 2026-11-08
"""

from models.engagement_cleanup import purge_orphans
from models.migrations.rebuild import EVIDENCE_LINK_QUERIES, raise_sequence, rebuild, table_sql

# The manager runs this migration with foreign keys off: dropping a parent table
# with them on would delete its children through ON DELETE CASCADE (L-32).
FOREIGN_KEYS_OFF = True

# table -> (columns elsewhere that hold its IDs, audit resource_type, typed links)
_REFERENCES = {
    'engagements': (('engagement_id',), 'engagement', ()),
    'evidence': (('evidence_id', 'start_evidence_id', 'end_evidence_id'), 'evidence', EVIDENCE_LINK_QUERIES),
}


def upgrade(db):
    cursor = db.cursor()
    for table in ('engagements', 'evidence'):
        if rebuild(cursor, table, autoincrement=True):
            print(f"  -> {table} now uses AUTOINCREMENT")
    for table, (columns, audit_type, links) in _REFERENCES.items():
        if table_sql(cursor, table):
            raise_sequence(cursor, table, columns, audit_type, links)
    removed = purge_orphans(cursor)
    if removed:
        print(f"  -> Removed {removed} row(s) left by deleted engagements")
    db.commit()
    print("  ✓ Engagement and evidence IDs are no longer reused")


def downgrade(db):
    cursor = db.cursor()
    for table in ('engagements', 'evidence'):
        rebuild(cursor, table, autoincrement=False)
        cursor.execute('DELETE FROM sqlite_sequence WHERE name = ?', (table,))
    db.commit()

"""
Migration 036: never reuse host IDs; drop links to deleted records (M-16, L-36)

hosts was declared "id INTEGER PRIMARY KEY" and host delete removed only the
hosts row, so the next host created, in any engagement, took the deleted
host's ID together with its credentials, notes, ports and evidence links.

- hosts is rebuilt with AUTOINCREMENT (models/migrations/rebuild.py), its
  sequence starting above every host ID still referenced (host_id columns,
  attack-map host references, the audit log).
- The evidence sequence is raised again, now also counting evidence IDs held by
  relationships and attack-map nodes, which 034 missed (L-36).
- Rows left by the old deletes are removed (purge_orphans): host children,
  executions of deleted hosts, relationships and map references to records
  that are gone.

Created: 2026-11-08
"""

from models.engagement_cleanup import purge_orphans
from models.migrations.rebuild import EVIDENCE_LINK_QUERIES, HOST_LINK_QUERIES, raise_sequence, rebuild, table_sql

FOREIGN_KEYS_OFF = True     # the manager turns them off around the rebuild (L-32)


def upgrade(db):
    cursor = db.cursor()
    if rebuild(cursor, 'hosts', autoincrement=True):
        print("  -> hosts now uses AUTOINCREMENT")
    if table_sql(cursor, 'hosts'):
        raise_sequence(cursor, 'hosts', ('host_id',), 'host', HOST_LINK_QUERIES)
    if table_sql(cursor, 'evidence'):
        raise_sequence(cursor, 'evidence', ('evidence_id', 'start_evidence_id', 'end_evidence_id'), 'evidence',
                       EVIDENCE_LINK_QUERIES)
    removed = purge_orphans(cursor)
    if removed:
        print(f"  -> Removed {removed} row(s) left by earlier deletes")
    db.commit()
    print("  ✓ Host IDs are no longer reused")


def downgrade(db):
    cursor = db.cursor()
    rebuild(cursor, 'hosts', autoincrement=False)
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'hosts'")
    db.commit()

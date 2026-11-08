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

Runs inside the migration manager's transaction. Foreign keys are not enforced
in PTVault databases; where they are (tests), checks are deferred to the commit,
by which time the rebuilt tables hold the same IDs.

Created: 2026-11-08
"""

import re

from models.engagement_cleanup import purge_orphans

# table -> columns elsewhere that hold its IDs (the sequence starts above all of them)
_REFERENCES = {
    'engagements': ('engagement_id',),
    'evidence': ('evidence_id', 'start_evidence_id', 'end_evidence_id'),
}


_AUDIT_TYPE = {'engagements': 'engagement', 'evidence': 'evidence'}


def _table_sql(cursor, table):
    row = cursor.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row[0] if row else None


def _rebuild(cursor, table, autoincrement):
    sql = _table_sql(cursor, table)
    if sql is None or ('AUTOINCREMENT' in sql.upper()) == autoincrement:
        return False
    if autoincrement:
        new_sql, n = re.subn(r'\bid\s+INTEGER\s+PRIMARY\s+KEY\b', 'id INTEGER PRIMARY KEY AUTOINCREMENT', sql,
                             count=1, flags=re.IGNORECASE)
    else:
        new_sql, n = re.subn(r'\s+AUTOINCREMENT\b', '', sql, count=1, flags=re.IGNORECASE)
    if n != 1:
        raise RuntimeError(f'Cannot find the id column of {table}')
    temp = f'{table}__rebuild'
    new_sql, n = re.subn(rf'^\s*CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?["`\[]?{table}["`\]]?', f'CREATE TABLE {temp}',
                         new_sql, count=1, flags=re.IGNORECASE)
    if n != 1:
        raise RuntimeError(f'Cannot rename {table} for the rebuild')

    # Indexes and triggers go with the dropped table; keep their definitions
    extras = [row[0] for row in cursor.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type IN ('index', 'trigger') AND sql IS NOT NULL",
        (table,))]
    # Generated columns (hidden 2 or 3) are computed, not copied
    columns = [row[1] for row in cursor.execute(f'PRAGMA table_xinfo({table})') if row[6] == 0]
    column_list = ', '.join(f'"{c}"' for c in columns)

    cursor.execute(f'DROP TABLE IF EXISTS {temp}')
    cursor.execute(new_sql)
    cursor.execute(f'INSERT INTO {temp} ({column_list}) SELECT {column_list} FROM {table}')
    cursor.execute(f'DROP TABLE {table}')
    cursor.execute(f'ALTER TABLE {temp} RENAME TO {table}')
    for statement in extras:
        cursor.execute(statement)
    return True


def _raise_sequence(cursor, table):
    """Start the AUTOINCREMENT sequence above every ID of this table still referenced."""
    floor = cursor.execute(f'SELECT COALESCE(MAX(id), 0) FROM {table}').fetchone()[0]
    tables = [row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%fts%'")]
    for other in tables:
        columns = {row[1] for row in cursor.execute(f'PRAGMA table_info({other})')}
        for column in set(_REFERENCES[table]) & columns:
            value = cursor.execute(
                f"SELECT MAX({column}) FROM {other} WHERE typeof({column}) = 'integer'").fetchone()[0]
            floor = max(floor, value or 0)
    # The audit trail names IDs too (resource_type 'engagement' / 'evidence')
    if 'audit_log' in tables:
        value = cursor.execute("SELECT MAX(resource_id) FROM audit_log WHERE resource_type = ? "
                               "AND typeof(resource_id) = 'integer'", (_AUDIT_TYPE[table],)).fetchone()[0]
        floor = max(floor, value or 0)
    row = cursor.execute('SELECT seq FROM sqlite_sequence WHERE name = ?', (table,)).fetchone()
    if row is None:
        cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)', (table, floor))
    elif row[0] < floor:
        cursor.execute('UPDATE sqlite_sequence SET seq = ? WHERE name = ?', (floor, table))


def upgrade(db):
    cursor = db.cursor()
    cursor.execute('PRAGMA defer_foreign_keys = ON')
    for table in ('engagements', 'evidence'):
        if _rebuild(cursor, table, autoincrement=True):
            print(f"  -> {table} now uses AUTOINCREMENT")
    for table in ('engagements', 'evidence'):
        if _table_sql(cursor, table):
            _raise_sequence(cursor, table)
    removed = purge_orphans(cursor)
    if removed:
        print(f"  -> Removed {removed} row(s) left by deleted engagements")
    db.commit()
    print("  ✓ Engagement and evidence IDs are no longer reused")


def downgrade(db):
    cursor = db.cursor()
    cursor.execute('PRAGMA defer_foreign_keys = ON')
    for table in ('engagements', 'evidence'):
        _rebuild(cursor, table, autoincrement=False)
        cursor.execute('DELETE FROM sqlite_sequence WHERE name = ?', (table,))
    db.commit()

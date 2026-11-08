"""Table rebuilds for migrations that change a table's definition (M-13, M-16).

SQLite cannot add AUTOINCREMENT to an existing table, so the table is rebuilt:
copy the stored columns into a new table, drop the old one, rename, and recreate
its indexes and triggers. Generated columns are recomputed, not copied.

A migration that rebuilds a table sets FOREIGN_KEYS_OFF = True: the migration
manager then turns foreign keys off around it (outside the transaction, as
SQLite requires), because dropping a parent table with foreign keys on deletes
its children through ON DELETE CASCADE (L-32).
"""

import re


def table_sql(cursor, table):
    row = cursor.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row[0] if row else None


def rebuild(cursor, table, autoincrement):
    """Rebuild table with (or without) AUTOINCREMENT on its id; False if nothing to do."""
    sql = table_sql(cursor, table)
    if sql is None or ('AUTOINCREMENT' in sql.upper()) == autoincrement:
        return False
    if cursor.execute('PRAGMA foreign_keys').fetchone()[0]:
        raise RuntimeError(f'Rebuilding {table} needs foreign keys off (set FOREIGN_KEYS_OFF in the migration)')
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


def raise_sequence(cursor, table, columns, audit_type=None, extra_queries=()):
    """Start table's AUTOINCREMENT sequence above every one of its IDs still referenced.

    columns: column names that hold this table's IDs anywhere in the schema;
    audit_type: audit_log.resource_type naming this table; extra_queries: SQL
    returning one MAX() for references that need a condition (typed links).
    """
    floor = cursor.execute(f'SELECT COALESCE(MAX(id), 0) FROM {table}').fetchone()[0]
    tables = [row[0] for row in cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%fts%'")]
    for other in tables:
        present = {row[1] for row in cursor.execute(f'PRAGMA table_info({other})')}
        for column in set(columns) & present:
            value = cursor.execute(
                f"SELECT MAX({column}) FROM {other} WHERE typeof({column}) = 'integer'").fetchone()[0]
            floor = max(floor, value or 0)
    queries = list(extra_queries)
    if audit_type and 'audit_log' in tables:
        queries.append(("SELECT MAX(resource_id) FROM audit_log WHERE resource_type = ? "
                        "AND typeof(resource_id) = 'integer'", (audit_type,)))
    for query in queries:
        sql, params = query if isinstance(query, tuple) else (query, ())
        try:
            value = cursor.execute(sql, params).fetchone()[0]
        except Exception:                      # a table this install does not have
            value = None
        floor = max(floor, value or 0)
    row = cursor.execute('SELECT seq FROM sqlite_sequence WHERE name = ?', (table,)).fetchone()
    if row is None:
        cursor.execute('INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)', (table, floor))
    elif row[0] < floor:
        cursor.execute('UPDATE sqlite_sequence SET seq = ? WHERE name = ?', (floor, table))
    return floor


# Evidence IDs held by typed links, which a plain *evidence_id column scan misses (L-36)
EVIDENCE_LINK_QUERIES = (
    "SELECT MAX(source_node_id) FROM node_relationships WHERE source_node_type = 'evidence'",
    "SELECT MAX(target_node_id) FROM node_relationships WHERE target_node_type = 'evidence'",
    "SELECT MAX(ref_id) FROM attack_map_nodes WHERE ref_type = 'evidence' AND typeof(ref_id) = 'integer'",
)
HOST_LINK_QUERIES = (
    "SELECT MAX(ref_id) FROM attack_map_nodes WHERE ref_type = 'host' AND typeof(ref_id) = 'integer'",
)

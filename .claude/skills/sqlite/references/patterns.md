# SQLite Patterns Reference

## Contents
- Schema Design Patterns
- FTS4 Full-Text Search
- Generated Columns for JSON
- Index Strategy
- Anti-Patterns

## Schema Design Patterns

### Engagement Isolation

Every user-data table has `engagement_id` with a foreign key and index. The `BaseDAO` adds this filter automatically when `engagement_scoped=True`.

```sql
-- From models/schema.sql
CREATE TABLE IF NOT EXISTS hosts (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL,
    ip TEXT NOT NULL,
    hostname TEXT,
    FOREIGN KEY(engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
    UNIQUE(engagement_id, ip)
);

CREATE INDEX IF NOT EXISTS idx_hosts_engagement ON hosts(engagement_id);
```

Tables without engagement scoping: `users`, `user_sessions`, `atomics`, `atomics_metadata`, `writeups`, `test_plans`, `navigator_layers`, `tags`.

### UPSERT with COALESCE

Tool imports run multiple times. Use `ON CONFLICT ... DO UPDATE` to merge data:

```python
# From models/database.py:296-303
cursor.execute('''
    INSERT INTO hosts (engagement_id, ip, hostname, os)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(engagement_id, ip) DO UPDATE SET
        hostname = COALESCE(excluded.hostname, hosts.hostname),
        os = COALESCE(excluded.os, hosts.os),
        updated_at = CURRENT_TIMESTAMP
''', (engagement_id, ip, hostname, os))
```

`COALESCE(excluded.X, table.X)` keeps the existing value if the new one is NULL.

### Junction Tables

Many-to-many relationships use junction tables with composite primary keys:

```sql
-- From models/schema.sql
CREATE TABLE IF NOT EXISTS evidence_hosts (
    evidence_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    source TEXT DEFAULT 'manual',
    PRIMARY KEY (evidence_id, host_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE
);
```

Use `INSERT OR IGNORE` for idempotent linking:

```python
cursor.execute('''
    INSERT OR IGNORE INTO evidence_hosts (evidence_id, host_id, source)
    VALUES (?, ?, 'auto')
''', (evidence_id, host_id))
```

## FTS4 Full-Text Search

### CRITICAL: FTS4 (Not FTS5)

PTVault uses FTS4 because pysqlcipher3 does not compile FTS5. NEVER use FTS5 syntax (`bm25()`, `highlight()`, content-sync via `content=`).

### FTS4 Table Definition

```sql
-- From models/schema.sql:226-231
CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts4(
    title,
    content,
    metadata,
    tokenize=unicode61
);
```

### Sync Triggers (docid-based)

PTVault's triggers use `docid` — not `rowid`:

```sql
-- From models/schema.sql:234-257
CREATE TRIGGER IF NOT EXISTS evidence_fts_insert
AFTER INSERT ON evidence BEGIN
    INSERT INTO evidence_fts(docid, title, content, metadata)
    VALUES (new.id, new.title, new.content, new.metadata);
END;

CREATE TRIGGER IF NOT EXISTS evidence_fts_update
AFTER UPDATE ON evidence BEGIN
    UPDATE evidence_fts
    SET title = new.title, content = new.content, metadata = new.metadata
    WHERE docid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS evidence_fts_delete
AFTER DELETE ON evidence BEGIN
    DELETE FROM evidence_fts WHERE docid = old.id;
END;
```

### FTS4 Query Pattern

```python
# From models/dao/evidence_dao.py:153-161
cursor.execute('''
    SELECT e.* FROM evidence e
    JOIN evidence_fts fts ON e.id = fts.docid
    WHERE e.engagement_id = ? AND fts MATCH ?
    LIMIT ?
''', (self.engagement_id, query, limit))
```

### Rebuilding the FTS Index

```python
# FTS4 rebuild syntax (different from FTS5)
cursor.execute("INSERT INTO evidence_fts(evidence_fts) VALUES('rebuild')")
```

## Generated Columns for JSON

SQLite 3.31+ stored generated columns extract frequently-queried JSON fields:

```python
# From models/database.py:98-118
cursor.execute('''
    ALTER TABLE evidence
    ADD COLUMN tool_name TEXT GENERATED ALWAYS AS (
        json_extract(metadata, '$.tool')
    ) STORED
''')

cursor.execute('''
    ALTER TABLE evidence
    ADD COLUMN severity_level TEXT GENERATED ALWAYS AS (
        CASE
            WHEN CAST(json_extract(metadata, '$.summary.by_severity.Critical') AS INTEGER) > 0 THEN 'critical'
            WHEN CAST(json_extract(metadata, '$.summary.by_severity.High') AS INTEGER) > 0 THEN 'high'
            WHEN CAST(json_extract(metadata, '$.summary.by_severity.Medium') AS INTEGER) > 0 THEN 'medium'
            WHEN CAST(json_extract(metadata, '$.summary.by_severity.Low') AS INTEGER) > 0 THEN 'low'
            ELSE NULL
        END
    ) STORED
''')
```

These columns are indexed and queryable like normal columns. NEVER write to them directly.

## Index Strategy

### Composite Indexes (Migration 009)

```sql
-- Covers: WHERE engagement_id = ? AND evidence_type = ?
CREATE INDEX idx_evidence_engagement_type ON evidence(engagement_id, evidence_type);

-- Covers: WHERE engagement_id = ? ORDER BY created_at DESC
CREATE INDEX idx_evidence_engagement_created ON evidence(engagement_id, created_at DESC);

-- Covers: WHERE host_id = ? ORDER BY port ASC
CREATE INDEX idx_host_ports_host_port ON host_ports(host_id, port ASC);
```

### Verify Index Usage

```python
cursor.execute('EXPLAIN QUERY PLAN SELECT * FROM hosts WHERE engagement_id = ?', (1,))
# GOOD: "SEARCH hosts USING INDEX idx_hosts_engagement"
# BAD:  "SCAN hosts"
```

## Anti-Patterns

### WARNING: SQL Injection via String Formatting

```python
# BAD — SQL injection
cursor.execute(f"SELECT * FROM hosts WHERE ip = '{user_input}'")

# GOOD — parameterized
cursor.execute('SELECT * FROM hosts WHERE ip = ?', (user_input,))
```

### WARNING: Missing Engagement Isolation

```python
# BAD — leaks data across engagements
cursor.execute('SELECT * FROM hosts WHERE id = ?', (host_id,))

# GOOD — always scope by engagement_id
cursor.execute('SELECT * FROM hosts WHERE id = ? AND engagement_id = ?',
               (host_id, g.active_engagement_id))
```

**When You Might Be Tempted:** Quick debugging or admin endpoints. Use `BaseDAO` instead — it enforces scoping automatically.

### WARNING: Committing Inside Loops

```python
# BAD — 1000 commits for 1000 hosts, ~100x slower
for host in hosts:
    cursor.execute('INSERT INTO hosts ...', (host,))
    db.commit()

# GOOD — single transaction
try:
    for host in hosts:
        cursor.execute('INSERT INTO hosts ...', (host,))
    db.commit()
except Exception:
    db.rollback()
    raise
```

### WARNING: LIKE with Leading Wildcard

```python
# BAD — full table scan, cannot use indexes
cursor.execute("SELECT * FROM evidence WHERE tags LIKE ?", ('%critical%',))

# GOOD — use FTS4 for text search
cursor.execute('''
    SELECT e.* FROM evidence e
    JOIN evidence_fts fts ON e.id = fts.docid
    WHERE e.engagement_id = ? AND fts MATCH ?
''', (engagement_id, 'critical'))
```

### WARNING: Using FTS5 Syntax with FTS4

```python
# BAD — bm25() and highlight() are FTS5-only
cursor.execute("SELECT *, bm25(evidence_fts) FROM evidence_fts WHERE MATCH ?")

# GOOD — FTS4 uses rank and snippet()
cursor.execute('''
    SELECT e.*, snippet(evidence_fts, '<b>', '</b>', '...', -1, 64) as snippet
    FROM evidence e
    JOIN evidence_fts fts ON e.id = fts.docid
    WHERE fts MATCH ?
''', (query,))
```

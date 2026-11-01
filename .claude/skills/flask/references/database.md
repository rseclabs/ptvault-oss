# Database Reference

## Contents
- Connection Management
- Query Patterns
- Transaction Handling
- Migration System
- N+1 Prevention
- Anti-Patterns

## Connection Management

Connections are per-request, established by `@require_auth` and closed on teardown.

### Setup (middleware/auth.py:179-185)

```python
# @require_auth establishes the connection
g.db = get_db_connection()
run_migrations_on_connection(g.db)
```

### Teardown (app.py:128-133)

```python
@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

### get_db_connection (models/database.py:6-30)

```python
def get_db_connection(key=None):
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enables dict(row) conversion
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
    return conn
```

**Key detail:** `row_factory = sqlite3.Row` means cursor results support both `row[0]` indexing and `dict(row)` conversion. The DAO layer uses `dict(row)`, while older route code uses positional indexing.

## Query Patterns

### Always Use Parameterized Queries

```python
# Safe - parameterized
cursor.execute('SELECT * FROM hosts WHERE engagement_id = ? AND ip = ?',
               (engagement_id, ip))

# NEVER do this
cursor.execute(f"SELECT * FROM hosts WHERE ip = '{user_input}'")
```

### Dynamic IN Clauses

From `routes/hosts.py:836-843` (port grid endpoint):

```python
host_ids = [1, 2, 3, 4, 5]
placeholders = ','.join('?' * len(host_ids))
cursor.execute(f'''
    SELECT host_id, port, protocol, state, service
    FROM host_ports
    WHERE host_id IN ({placeholders})
    ORDER BY port ASC
''', host_ids)
```

### UPSERT Pattern

From `utils/host_extractor.py` — insert or update in one statement:

```python
cursor.execute('''
    INSERT INTO hosts (engagement_id, ip, hostname, os)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(engagement_id, ip) DO UPDATE SET
        hostname = COALESCE(excluded.hostname, hosts.hostname),
        os = COALESCE(excluded.os, hosts.os),
        updated_at = CURRENT_TIMESTAMP
    RETURNING id
''', (engagement_id, ip, hostname, os))
host_id = cursor.fetchone()[0]
```

### Row-to-Dict Conversion

Two patterns coexist:

```python
# Old pattern: positional indexing (routes/hosts.py)
host = {
    "id": row[0],
    "ip": row[2],
    "hostname": row[3],
}

# New pattern: dict conversion via sqlite3.Row (DAO layer)
host = dict(row)  # Works because row_factory = sqlite3.Row
```

Prefer `dict(row)` for new code. The old positional pattern is fragile — adding a column to the SELECT breaks all index references.

## Transaction Handling

### Commit After All Operations Succeed

```python
try:
    cursor = g.db.cursor()
    cursor.execute('INSERT INTO hosts ...', values)
    cursor.execute('INSERT INTO host_ports ...', port_values)
    g.db.commit()  # Commit only after both succeed
    return jsonify(result), 201
except Exception as e:
    g.db.rollback()  # Rollback both on any failure
    return jsonify({"error": str(e)}), 500
```

### Constraint Violation Handling

From `routes/hosts.py:684-688`:

```python
except Exception as e:
    if 'UNIQUE constraint failed' in str(e):
        return jsonify({"error": "Port already exists for this host"}), 409
    g.db.rollback()
    return jsonify({"error": str(e)}), 500
```

## Migration System

PTVault has two migration mechanisms:

1. **Versioned migrations** in `models/migrations/versions/` — managed by `MigrationManager`
2. **Legacy inline migrations** in `middleware/auth.py:12-152` — `CREATE TABLE IF NOT EXISTS` on first auth request

### Versioned Migrations (Preferred)

See the **sqlite** skill for migration file format.

```python
# models/migrations/versions/016_add_new_table.py
def upgrade(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS new_table (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_new_table_engagement ON new_table(engagement_id)')
```

### Adding Columns Safely

```python
# Use try/except for ALTER TABLE — SQLite has no IF NOT EXISTS for columns
try:
    cursor.execute('ALTER TABLE hosts ADD COLUMN new_field TEXT DEFAULT NULL')
except Exception:
    pass  # Column already exists
```

## N+1 Prevention

### Batch Load with IN Clause

From `routes/hosts.py:804-871` (port grid endpoint):

```python
# 1. Get all hosts in one query
cursor.execute('SELECT id, ip, hostname FROM hosts WHERE engagement_id = ?',
               (engagement_id,))
hosts = cursor.fetchall()
host_ids = [h[0] for h in hosts]

# 2. Get ALL ports for ALL hosts in one query
if host_ids:
    placeholders = ','.join('?' * len(host_ids))
    cursor.execute(f'''
        SELECT host_id, port, protocol, state, service
        FROM host_ports WHERE host_id IN ({placeholders})
    ''', host_ids)

    # 3. Build lookup dict
    ports_by_host = {}
    for row in cursor.fetchall():
        ports_by_host.setdefault(row[0], []).append(dict(row))
```

### Use JOINs with GROUP_CONCAT

From `routes/engagements.py:97-111`:

```python
cursor.execute('''
    SELECT e.id, e.title, e.content,
           GROUP_CONCAT(t.name, ',') as tag_names
    FROM evidence e
    LEFT JOIN evidence_tags et ON e.id = et.evidence_id
    LEFT JOIN tags t ON et.tag_id = t.id
    WHERE e.engagement_id = ?
    GROUP BY e.id
    ORDER BY e.created_at DESC
''', (engagement_id,))
```

## WARNING: Anti-Patterns

### Never Commit Inside Loops

**The Problem:**

```python
for item in items:
    cursor.execute('INSERT INTO items ...', (item,))
    g.db.commit()  # One filesystem sync per item
```

**Why This Breaks:** Each `commit()` forces a filesystem sync (fsync). With WAL mode and 1000 items, this is ~1000x slower than a single commit.

**The Fix:**

```python
for item in items:
    cursor.execute('INSERT INTO items ...', (item,))
g.db.commit()  # Single commit for all items
```

### Never Use Bare `except` for Migrations

**The Problem:**

```python
try:
    cursor.execute('ALTER TABLE items ADD COLUMN new_field TEXT')
except:
    pass  # Swallows ALL exceptions including syntax errors
```

**Why This Breaks:** If the SQL has a typo, you silently ignore it and the column never gets created.

**The Fix:**

```python
try:
    cursor.execute('ALTER TABLE items ADD COLUMN new_field TEXT')
except Exception:
    pass  # Column already exists — acceptable for idempotent migrations
```

Using `except Exception` instead of bare `except` still allows `KeyboardInterrupt` and `SystemExit` to propagate.

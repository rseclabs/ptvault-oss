# SQLite Workflows Reference

## Contents
- Creating a Migration
- Adding a New Table
- Adding FTS to a Table
- Query Optimization
- Testing Database Code

## Creating a Migration

PTVault uses versioned migrations in `models/migrations/versions/`. Each file has an `upgrade(db)` and optional `downgrade(db)` function. The `MigrationManager` tracks applied versions in `schema_migrations`.

### Migration File Template

Create `models/migrations/versions/NNN_description.py`:

```python
"""
Migration NNN: Description of changes

Created: YYYY-MM-DD
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Check existence before creating (idempotent)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='new_table'")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE new_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engagement_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX idx_new_table_engagement ON new_table(engagement_id)')

    db.commit()
    print("  Migration NNN applied")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()
    cursor.execute('DROP INDEX IF EXISTS idx_new_table_engagement')
    cursor.execute('DROP TABLE IF EXISTS new_table')
    db.commit()
    print("  Migration NNN rolled back")
```

### Adding a Column Migration

```python
def upgrade(db):
    cursor = db.cursor()

    # Check if column exists before adding — SQLite has no IF NOT EXISTS for ALTER TABLE
    cursor.execute("SELECT COUNT(*) FROM pragma_table_info('hosts') WHERE name = 'priority'")
    if cursor.fetchone()[0] == 0:
        cursor.execute('ALTER TABLE hosts ADD COLUMN priority TEXT DEFAULT NULL')

    db.commit()
```

### Adding Indexes Migration (reference: migration 009)

```python
def upgrade(db):
    cursor = db.cursor()

    # Check existing indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    existing = {row[0] for row in cursor.fetchall()}

    if 'idx_evidence_engagement_type' not in existing:
        cursor.execute('CREATE INDEX idx_evidence_engagement_type ON evidence(engagement_id, evidence_type)')

    db.commit()
```

### Migration Checklist

Copy this checklist and track progress:
- [ ] Create `models/migrations/versions/NNN_description.py` with `upgrade()` and `downgrade()`
- [ ] Update `models/schema.sql` to reflect the final schema state
- [ ] Test on fresh database: `rm data/ptvault.db && python app.py`
- [ ] Test on existing database with data (run `python app.py`)
- [ ] Verify with `python -m pytest tests/test_migrations.py -v`

### Validation Loop

1. Write migration file
2. Run: `python -c "from models.database import get_db_connection; from models.migrations import apply_migrations; apply_migrations(get_db_connection())"`
3. Verify schema: `sqlite3 data/ptvault.db ".schema table_name"`
4. If wrong, fix migration and delete `schema_migrations` row, repeat step 2
5. Only proceed when verification passes

## Adding a New Table

Full workflow from schema to API. See the **flask** skill for route setup and the **python** skill for DAO creation.

### Step 1: Add to schema.sql

```sql
-- models/schema.sql — append at end
CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    host_id INTEGER,
    title TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    description TEXT,
    remediation TEXT,
    cvss_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_engagement ON findings(engagement_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
```

### Step 2: Create Migration

```python
# models/migrations/versions/016_add_findings_table.py
def upgrade(db):
    cursor = db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='findings'")
    if not cursor.fetchone():
        cursor.execute('''CREATE TABLE findings (...)''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_findings_engagement ON findings(engagement_id)')
    db.commit()

def downgrade(db):
    cursor = db.cursor()
    cursor.execute('DROP TABLE IF EXISTS findings')
    db.commit()
```

### Step 3: Create DAO

```python
# models/dao/findings_dao.py
from models.dao.base import BaseDAO

class FindingsDAO(BaseDAO):
    def __init__(self):
        super().__init__('findings', engagement_scoped=True)

    def find_by_severity(self, severity):
        return self.find_all({'severity': severity}, order_by='created_at DESC')

    def find_by_host(self, host_id):
        return self.find_all({'host_id': host_id}, order_by='severity')
```

## Adding FTS to a Table

### Step 1: Create FTS Virtual Table

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS writeups_fts USING fts4(
    name,
    description,
    remediation,
    tags,
    tokenize=unicode61
);
```

### Step 2: Add Sync Triggers

```sql
CREATE TRIGGER IF NOT EXISTS writeups_fts_insert
AFTER INSERT ON writeups BEGIN
    INSERT INTO writeups_fts(docid, name, description, remediation, tags)
    VALUES (new.id, new.name, new.description, new.remediation, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS writeups_fts_update
AFTER UPDATE ON writeups BEGIN
    UPDATE writeups_fts
    SET name = new.name, description = new.description,
        remediation = new.remediation, tags = new.tags
    WHERE docid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS writeups_fts_delete
AFTER DELETE ON writeups BEGIN
    DELETE FROM writeups_fts WHERE docid = old.id;
END;
```

### Step 3: Backfill Existing Data

```python
cursor.execute('''
    INSERT INTO writeups_fts(docid, name, description, remediation, tags)
    SELECT id, name, description, remediation, tags FROM writeups
''')
```

### Step 4: Query with MATCH

```python
def search_writeups(query, limit=20):
    cursor = g.db.cursor()
    cursor.execute('''
        SELECT w.* FROM writeups w
        JOIN writeups_fts fts ON w.id = fts.docid
        WHERE fts MATCH ?
        LIMIT ?
    ''', (query, limit))
    return [dict(row) for row in cursor.fetchall()]
```

## Query Optimization

### Avoiding N+1 Queries

```python
# BAD — one query per host
hosts = cursor.execute('SELECT * FROM hosts WHERE engagement_id = ?', (eid,)).fetchall()
for host in hosts:
    ports = cursor.execute('SELECT * FROM host_ports WHERE host_id = ?', (host['id'],)).fetchall()

# GOOD — single JOIN
cursor.execute('''
    SELECT h.ip, p.port, p.state, p.service
    FROM hosts h
    LEFT JOIN host_ports p ON h.id = p.host_id
    WHERE h.engagement_id = ?
    ORDER BY h.ip, p.port
''', (engagement_id,))
```

### Dynamic Query Builder Pattern

From `models/dao/evidence_dao.py:163-261` — build WHERE clauses dynamically with parameterized values:

```python
where_clauses = ['e.engagement_id = ?']
params = [self.engagement_id]

if evidence_type:
    where_clauses.append('e.evidence_type = ?')
    params.append(evidence_type)

if tool:
    where_clauses.append('e.tool_name = ?')
    params.append(tool)

where_sql = ' WHERE ' + ' AND '.join(where_clauses)
query = f'SELECT * FROM evidence e{where_sql} ORDER BY e.created_at DESC LIMIT ? OFFSET ?'
params.extend([limit, offset])
cursor.execute(query, params)
```

NEVER use string formatting for values. Column/table names in f-strings are acceptable when they come from controlled code (not user input).

## Testing Database Code

### Test Fixture (from tests/conftest.py pattern)

```python
import pytest
import sqlite3

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    # Load schema
    with open('models/schema.sql') as f:
        # Execute statements individually (triggers contain semicolons)
        # Use init_db pattern from models/database.py for production-like setup
        pass

    # Or use init_db directly
    from models.database import init_db
    init_db()

    yield db
    db.close()
```

### Testing Migrations

```python
def test_migration_is_idempotent(test_db):
    """Migration must be safe to run multiple times."""
    from models.migrations.versions import NNN_description as migration

    migration.upgrade(test_db)
    migration.upgrade(test_db)  # Should not raise

    # Verify schema
    cursor = test_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='new_table'")
    assert cursor.fetchone() is not None
```

See the **python** skill for DAO test patterns.

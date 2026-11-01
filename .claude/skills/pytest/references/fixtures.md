# Fixtures Reference

## Contents
- conftest.py Shared Fixtures
- Database Fixtures
- Sample Data Fixtures
- File Fixtures
- Fixture Scope and Performance
- Anti-Patterns

## conftest.py Shared Fixtures

PTVault's shared fixtures live in `tests/conftest.py`. These are auto-discovered by pytest.

### Core Database Fixture

```python
import sqlite3
import pytest

@pytest.fixture
def test_db():
    """In-memory SQLite database with base schema."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE engagements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, client TEXT, short_name TEXT,
        start_date TEXT, end_date TEXT, status TEXT,
        scope TEXT, contact_name TEXT, contact_email TEXT,
        notes TEXT, tags TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER, type TEXT, title TEXT,
        content TEXT, tags TEXT, metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE hosts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER, ip TEXT, hostname TEXT, os TEXT,
        rooted INTEGER DEFAULT 0, shell INTEGER DEFAULT 0,
        interested INTEGER DEFAULT 0, color_category TEXT
    )''')
    conn.execute('''CREATE TABLE engagement_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engagement_id INTEGER, name TEXT, category TEXT,
        criticality TEXT, cvss_score REAL, description TEXT,
        remediation TEXT
    )''')
    conn.execute('''CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'editor'
    )''')
    conn.execute('''CREATE TABLE report_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, category TEXT, structure TEXT
    )''')
    conn.commit()
    yield conn
    conn.close()
```

### Sample Engagement Fixture

```python
@pytest.fixture
def sample_engagement(test_db):
    """Pre-populated engagement with hosts, findings, and evidence."""
    cursor = test_db.cursor()
    cursor.execute(
        "INSERT INTO engagements (name, client, status) VALUES (?, ?, ?)",
        ('Test Engagement', 'ACME Corp', 'active')
    )
    eng_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO hosts (engagement_id, ip, hostname, os) VALUES (?, ?, ?, ?)",
        (eng_id, '192.168.1.10', 'webserver', 'Ubuntu 22.04')
    )
    cursor.execute(
        "INSERT INTO hosts (engagement_id, ip, hostname, os) VALUES (?, ?, ?, ?)",
        (eng_id, '192.168.1.20', 'dc01', 'Windows Server 2019')
    )
    cursor.execute(
        "INSERT INTO engagement_findings (engagement_id, name, criticality, cvss_score, description, remediation) VALUES (?, ?, ?, ?, ?, ?)",
        (eng_id, 'SQL Injection', 'critical', 9.8, 'SQLi in login form', 'Use parameterized queries')
    )
    cursor.execute(
        "INSERT INTO engagement_findings (engagement_id, name, criticality, cvss_score, description, remediation) VALUES (?, ?, ?, ?, ?, ?)",
        (eng_id, 'Weak Password Policy', 'medium', 5.3, 'No complexity requirements', 'Enforce strong passwords')
    )
    test_db.commit()
    return eng_id
```

## Database Fixtures

### Minimal vs Full Schema

| Approach | When | Trade-off |
|----------|------|-----------|
| Inline `CREATE TABLE` | Unit tests for specific functions | Fast, but may miss schema drift |
| Load `models/schema.sql` | Integration/DAO tests | Slower setup, but catches real issues |
| Apply migrations on base | Migration tests | Tests the actual migration path |

### Full Schema Fixture

```python
import os

@pytest.fixture
def full_schema_db():
    """Database with the complete production schema."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    yield conn
    conn.close()
```

### On-Disk Database Fixture

Some tests need a real file (e.g., testing WAL mode, file locking, or migration manager):

```python
@pytest.fixture
def disk_db(tmp_path):
    """On-disk SQLite database for tests requiring file operations."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    yield conn, db_path
    conn.close()
```

## File Fixtures

Test data files live in `tests/fixtures/`. Currently contains:

| File | Purpose |
|------|---------|
| `sample_nmap.xml` | Valid Nmap XML output (1 host, 3 ports) |

### Adding New Fixture Files

Place static test data in `tests/fixtures/` and reference with:

```python
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
SAMPLE_NMAP_XML = os.path.join(FIXTURES_DIR, 'sample_nmap.xml')
```

For parser tests, provide both valid and edge-case fixture files.

### Dynamic Fixture Data

For tests that need custom XML/JSON, generate inline with `tmp_path`:

```python
@pytest.fixture
def nessus_xml(tmp_path):
    content = '''<?xml version="1.0"?>
    <NessusClientData_v2>
      <Report name="Test Scan">
        <ReportHost name="10.0.0.1">
          <ReportItem port="443" svc_name="https" severity="3">
            <pluginName>SSL Certificate Expired</pluginName>
            <description>The SSL certificate has expired.</description>
          </ReportItem>
        </ReportHost>
      </Report>
    </NessusClientData_v2>'''
    path = tmp_path / "scan.nessus"
    path.write_text(content)
    return str(path)
```

## Fixture Scope and Performance

### Default Scope: `function`

Every fixture recreates per test. This is correct for database fixtures (isolation) but wasteful for read-only data.

### Session Scope for Static Data

```python
@pytest.fixture(scope='session')
def nmap_fixture_path():
    """Path to sample Nmap XML - shared across all tests."""
    return os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_nmap.xml')
```

Use `scope='session'` only for immutable data (file paths, constants). NEVER for database connections or stateful objects.

## WARNING: Mutable Default Data in Fixtures

**The Problem:**

```python
# BAD - Returns same dict, mutations leak between tests
@pytest.fixture
def host_data():
    return {'ip': '10.0.0.1', 'hostname': 'web01'}

def test_one(host_data):
    host_data['os'] = 'Linux'  # Mutates the fixture return value

def test_two(host_data):
    assert 'os' not in host_data  # May fail depending on test order
```

**Why This Breaks:** With `function` scope this actually works (new dict each call), but developers assume it's shared and write confusing tests. With `session` scope, mutations leak.

**The Fix:** Always return fresh data. For `session`-scoped fixtures, return immutable values (paths, tuples) not mutable dicts.

## WARNING: Heavy Fixture Setup Without Reuse

**The Problem:**

```python
# BAD - Creates full schema + 50 records for a test that checks one field
@pytest.fixture
def test_db():
    conn = sqlite3.connect(':memory:')
    _create_19_tables(conn)
    _insert_50_hosts(conn)
    _insert_200_evidence(conn)
    return conn

def test_host_has_ip(test_db):
    row = test_db.execute('SELECT ip FROM hosts LIMIT 1').fetchone()
    assert row['ip'] is not None
```

**Why This Breaks:** Test suite becomes slow. Each test pays the cost of creating data it doesn't use.

**The Fix:** Layer fixtures. Use minimal base fixtures and compose them:

```python
@pytest.fixture
def test_db():
    """Bare database with schema only."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE hosts (id INTEGER PRIMARY KEY, ip TEXT, engagement_id INTEGER)')
    conn.commit()
    yield conn
    conn.close()

@pytest.fixture
def populated_db(test_db):
    """Database with sample data - use only when tests need pre-existing records."""
    test_db.execute("INSERT INTO hosts (ip, engagement_id) VALUES ('10.0.0.1', 1)")
    test_db.commit()
    return test_db
```

## Fixture Composition Checklist

Copy this when designing fixtures for a new test module:

- [ ] Identify minimum schema needed (tables, columns)
- [ ] Create base DB fixture with just the schema
- [ ] Create sample data fixture that builds on base DB
- [ ] Use `tmp_path` for any file-based test data
- [ ] Use `function` scope for all mutable fixtures
- [ ] Use `session` scope only for immutable paths/constants
- [ ] Place reusable fixtures in `tests/conftest.py`
- [ ] Place module-specific fixtures in the test file itself

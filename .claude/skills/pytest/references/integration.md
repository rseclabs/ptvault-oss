# Integration Test Reference

## Contents
- Flask Route Tests
- Migration Tests
- Multi-User and RBAC Tests
- Parser Auto-Detection Tests
- Database Integration Tests

## Flask Route Tests

Integration tests exercise the full request path: HTTP request -> Blueprint route -> `@require_auth` middleware -> DAO -> SQLite -> response.

### Pattern: Flask Test Client

PTVault doesn't currently have a full test client fixture. When adding one, follow this pattern:

```python
import pytest
from app import create_app  # If app factory exists, otherwise import app

@pytest.fixture
def client(tmp_path):
    import os
    os.environ['DATABASE_PATH'] = str(tmp_path / 'test.db')
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            from models.database import init_db
            init_db()
        yield client

@pytest.fixture
def auth_client(client):
    """Client with authenticated session."""
    client.post('/api/auth/setup', json={'master_password': 'TestPass123!'})
    client.post('/api/auth/login', json={'master_password': 'TestPass123!'})
    return client
```

### Testing Protected Routes

```python
def test_unauthenticated_request_rejected(client):
    resp = client.get('/api/engagements')
    assert resp.status_code == 401

def test_create_engagement(auth_client):
    resp = auth_client.post('/api/engagements', json={
        'name': 'Test Pentest',
        'client': 'ACME Corp',
        'status': 'active'
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['name'] == 'Test Pentest'
```

### Testing Evidence Search

```python
def test_evidence_search(auth_client, active_engagement):
    auth_client.post('/api/evidence', json={
        'type': 'note',
        'title': 'SQL Injection Found',
        'content': 'Found SQLi in login form',
        'tags': 'critical,sqli'
    })
    resp = auth_client.get('/api/evidence/search?q=SQL+injection')
    assert resp.status_code == 200
    results = resp.get_json()
    assert len(results) > 0
```

## Migration Tests

Migration tests verify that schema changes apply correctly and are idempotent. PTVault uses `unittest.TestCase` for these, but new migration tests should use pytest.

### Pattern: Migration Test With Temp DB

```python
import sqlite3
import os
import importlib.util

def load_migration(version_file):
    """Load a migration module by filename."""
    migration_dir = os.path.join(os.path.dirname(__file__), '..', 'models', 'migrations', 'versions')
    path = os.path.join(migration_dir, version_file)
    spec = importlib.util.spec_from_file_location(version_file.replace('.py', ''), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_migration_applies_cleanly(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Apply base schema first
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    # Apply specific migration
    migration = load_migration('015_some_feature.py')
    migration.upgrade(conn)
    conn.commit()
    # Verify the change
    cursor = conn.execute("PRAGMA table_info(new_table)")
    columns = [row[1] for row in cursor.fetchall()]
    assert 'expected_column' in columns
    conn.close()
```

### Testing Idempotent Migrations

```python
def test_migrations_are_idempotent(tmp_path):
    from models.migrations.manager import apply_migrations
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    _create_base_schema(conn)
    applied_1, failed_1 = apply_migrations(conn)
    applied_2, failed_2 = apply_migrations(conn)
    assert applied_2 == 0  # Nothing new to apply
    assert failed_2 == 0
    conn.close()
```

### Testing Migration Status

```python
def test_migration_status_reports_correctly(tmp_path):
    from models.migrations.manager import get_migration_status, apply_migrations
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    _create_base_schema(conn)
    status_before = get_migration_status(conn)
    assert status_before['pending'] > 0
    apply_migrations(conn)
    status_after = get_migration_status(conn)
    assert status_after['pending'] == 0
    assert status_after['applied'] == status_before['pending']
    conn.close()
```

## Multi-User and RBAC Tests

RBAC tests verify role hierarchy and engagement-level access control. See the **flask** skill for middleware details.

### Pattern: RBAC Logic Tests

```python
def test_role_hierarchy():
    hierarchy = {'admin': 3, 'editor': 2, 'viewer': 1}
    assert hierarchy['admin'] > hierarchy['editor']
    assert hierarchy['editor'] > hierarchy['viewer']

def test_admin_bypasses_engagement_membership():
    """Admins access all engagements without explicit membership."""
    role = 'admin'
    is_member = False
    has_access = (role == 'admin') or is_member
    assert has_access is True

def test_viewer_cannot_edit():
    """Viewers should be rejected by @require_engagement_access('editor')."""
    required = 'editor'
    user_role = 'viewer'
    hierarchy = {'admin': 3, 'editor': 2, 'viewer': 1}
    assert hierarchy[user_role] < hierarchy[required]
```

## Parser Auto-Detection Tests

The parser registry auto-detects tool type from file content. See the **xml-parsing** skill.

```python
from utils.parsers import detect_parser

def test_detect_nmap_from_xml(tmp_path):
    nmap_file = tmp_path / "scan.xml"
    nmap_file.write_text('<?xml version="1.0"?><nmaprun scanner="nmap" />')
    parser = detect_parser(str(nmap_file))
    assert parser is not None
    assert parser.__class__.__name__ == 'NmapToolParser'

def test_detect_unknown_returns_none(tmp_path):
    unknown = tmp_path / "data.txt"
    unknown.write_text('just some random text')
    assert detect_parser(str(unknown)) is None
```

## WARNING: Missing Flask Test Client Fixture

**Detected:** PTVault's `conftest.py` creates in-memory DB fixtures but lacks a Flask test client fixture. Route-level integration tests are limited.

**Impact:** Route logic, middleware decorators (`@require_auth`, `@require_role`), and error handling are untested at the HTTP layer. Auth bugs and middleware ordering issues slip through.

**Recommended:** Add a `client` fixture to `tests/conftest.py` using the pattern shown above. This enables testing the full request lifecycle including JWT cookie handling and engagement scoping.

## WARNING: No Test Coverage Tool Configured

**Detected:** No `pytest-cov` in `requirements.txt`.

**Impact:** No visibility into which code paths are untested. Critical parsers or DAO methods may have zero coverage.

**Recommended:**

```bash
pip install pytest-cov
python -m pytest tests/ --cov=. --cov-report=term-missing
```

Add to dev workflow to track coverage trends.

## Integration Test Checklist

Copy this checklist when adding integration tests:

- [ ] Test unauthenticated access returns 401
- [ ] Test authenticated happy path
- [ ] Test invalid input returns 400 with error message
- [ ] Test engagement isolation (can't access other engagement's data)
- [ ] Test RBAC (viewer can't write, editor can't admin)
- [ ] Test idempotency where applicable (migrations, imports)
- [ ] Verify response JSON structure matches API contract

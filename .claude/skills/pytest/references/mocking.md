# Mocking Reference

## Contents
- Monkeypatch for Flask g
- Temp Files for Parser Tests
- DAO Injection Pattern
- Migration Module Loading
- Anti-Patterns

## Monkeypatch for Flask g

DAOs and routes access `flask.g` for `g.db`, `g.active_engagement_id`, and `g.current_user`. When testing outside a Flask request context, mock `flask.g` with monkeypatch.

### Pattern: MockG Class

```python
import pytest
import flask

@pytest.fixture
def test_db():
    import sqlite3
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE engagements (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE evidence_relationships (
            id INTEGER PRIMARY KEY, engagement_id INTEGER,
            source_id INTEGER, target_id INTEGER,
            relationship_type TEXT, label TEXT
        );
        INSERT INTO engagements (id, name) VALUES (1, 'Test');
    ''')
    return conn

@pytest.fixture
def mock_g(test_db):
    class MockG:
        def __init__(self):
            self.db = test_db
            self.active_engagement_id = 1
            self.user_id = 1
            self.current_user = {'id': 1, 'username': 'admin', 'role': 'admin'}
            self.current_user_role = 'admin'
    return MockG()

def test_dao_with_mock_g(test_db, mock_g, monkeypatch):
    monkeypatch.setattr(flask, 'g', mock_g)
    from models.dao.relationship_dao import RelationshipDAO
    dao = RelationshipDAO()
    rel_id = dao.create_relationship(
        source_id=1, target_id=2,
        relationship_type='discovers', label='Test'
    )
    assert rel_id > 0
```

### When to Use Each Approach

| Approach | When | Example |
|----------|------|---------|
| `monkeypatch.setattr(flask, 'g', mock_g)` | Testing DAOs that read `flask.g` directly | Relationship, AttackMap DAOs |
| `app.test_request_context()` with `g.db = conn` | Testing DAOs via BaseDAO | BaseDAO CRUD tests |
| Direct DB injection: `dao.db = test_db` | DAO has `.db` attribute | TemplateDAO tests |

## Temp Files for Parser Tests

Parsers read files from disk. Use `tmp_path` (pytest built-in) or `tempfile` for test data.

### Pattern: tmp_path (Preferred)

```python
def test_validate_rejects_bad_xml(tmp_path):
    bad_file = tmp_path / "bad.xml"
    bad_file.write_text('<?xml version="1.0"?><notNmap/>')
    parser = NmapToolParser()
    assert parser.validate(str(bad_file)) is False
```

### Pattern: tempfile (Legacy, Avoid in New Tests)

```python
import tempfile
import os

def test_validate_old_style():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write('<?xml version="1.0"?><notNmap/>')
        temp_file = f.name
    try:
        parser = NmapToolParser()
        assert parser.validate(temp_file) is False
    finally:
        os.unlink(temp_file)
```

### WARNING: Using tempfile Instead of tmp_path

**The Problem:**

```python
# BAD - Manual cleanup, leaks files on assertion failure
with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
    f.write(content)
    temp_file = f.name
try:
    assert parser.validate(temp_file) is True
finally:
    os.unlink(temp_file)  # Skipped if assert raises before try block
```

**Why This Breaks:** If the test crashes between file creation and the `try` block, the temp file leaks. The `finally` block only runs if execution reaches `try`. Over time, `/tmp` fills with orphaned test files.

**The Fix:**

```python
# GOOD - pytest auto-cleans tmp_path after each test
def test_validate(tmp_path):
    test_file = tmp_path / "scan.xml"
    test_file.write_text(content)
    assert parser.validate(str(test_file)) is True
```

## DAO Injection Pattern

Some DAOs accept direct `.db` assignment, bypassing Flask context entirely. This is the simplest approach when a DAO supports it.

```python
@pytest.fixture
def template_dao(test_db):
    from models.dao.template_dao import TemplateDAO
    dao = TemplateDAO()
    dao.db = test_db
    return dao

def test_create_template(template_dao):
    template_id = template_dao.create({
        'name': 'Executive Report',
        'category': 'executive',
        'structure': '{"sections": []}'
    })
    assert template_id > 0
```

### WARNING: Mixing Injection With Flask Context

**The Problem:**

```python
# BAD - dao.db set manually but DAO also reads flask.g
dao = TemplateDAO()
dao.db = test_db
# Some methods still call g.active_engagement_id internally
dao.find_all()  # Crashes: AttributeError on g
```

**Why This Breaks:** Not all DAO methods use `self.db`. BaseDAO methods typically use `g.db`. If you inject `.db` but the method reads from `g`, you get confusing failures.

**The Fix:** Check which pattern the DAO uses. If it inherits from BaseDAO and uses `g.db`, use the Flask app context fixture instead:

```python
@pytest.fixture
def dao(app, db_connection):
    with app.test_request_context():
        g.db = db_connection
        g.active_engagement_id = 1
        yield TemplateDAO()
```

## Migration Module Loading

Migrations are standalone Python files loaded dynamically. Use `importlib.util` to load them in tests.

```python
import importlib.util
import os

def load_migration(filename):
    migrations_dir = os.path.join(
        os.path.dirname(__file__), '..', 'models', 'migrations', 'versions'
    )
    path = os.path.join(migrations_dir, filename)
    spec = importlib.util.spec_from_file_location(
        filename.replace('.py', ''), path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_migration_013_creates_relationships_table(test_db):
    migration = load_migration('013_evidence_relationships.py')
    migration.upgrade(test_db)
    test_db.commit()
    cursor = test_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_relationships'"
    )
    assert cursor.fetchone() is not None
```

## WARNING: Not Resetting State Between Tests

**The Problem:**

```python
# BAD - Class-level state leaks between tests
class TestParser:
    parser = NmapToolParser()  # Shared across all tests

    def test_one(self):
        self.parser.some_state = True

    def test_two(self):
        # self.parser.some_state is still True from test_one
```

**Why This Breaks:** Test order matters. Tests pass individually but fail when run together. CI becomes unreliable.

**The Fix:** Use `setup_method` for per-test initialization:

```python
class TestParser:
    def setup_method(self):
        self.parser = NmapToolParser()  # Fresh instance per test
```

Or use pytest fixtures with default `function` scope (which creates a new instance per test automatically).

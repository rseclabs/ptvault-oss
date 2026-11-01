# Unit Test Reference

## Contents
- DAO Unit Tests
- Parser Unit Tests
- Utility Function Tests
- Anti-Patterns
- Parametrized Tests

## DAO Unit Tests

DAOs depend on `flask.g` for database connection and engagement scoping. Unit tests must provide this context.

### Pattern: Flask App Context Fixture

```python
import sqlite3
import pytest
from flask import Flask, g
from models.dao.base import BaseDAO

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def db_connection(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''CREATE TABLE hosts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT NOT NULL,
        hostname TEXT,
        engagement_id INTEGER NOT NULL
    )''')
    conn.commit()
    return conn

@pytest.fixture
def dao(app, db_connection):
    with app.test_request_context():
        g.db = db_connection
        g.active_engagement_id = 1
        yield BaseDAO('hosts', engagement_scoped=True)
```

### Testing CRUD Operations

```python
def test_create_and_find(dao):
    host_id = dao.create({'ip': '10.0.0.1', 'hostname': 'web01'})
    assert host_id > 0
    host = dao.find_by_id(host_id)
    assert host['ip'] == '10.0.0.1'
    assert host['engagement_id'] == 1  # Auto-scoped

def test_update_respects_engagement(dao):
    host_id = dao.create({'ip': '10.0.0.1'})
    g.active_engagement_id = 2
    result = dao.update(host_id, {'ip': '10.0.0.2'})
    assert result is False  # Can't update another engagement's data

def test_delete_nonexistent(dao):
    assert dao.delete(9999) is False

def test_count_and_exists(dao):
    dao.create({'ip': '10.0.0.1'})
    assert dao.count() == 1
    assert dao.exists({'ip': '10.0.0.1'}) is True
    assert dao.exists({'ip': '10.0.0.99'}) is False
```

### Testing Engagement Isolation

This is the most critical property. Every engagement-scoped DAO test should verify isolation.

```python
def test_data_isolation(dao):
    dao.create({'ip': '10.0.0.1'})
    g.active_engagement_id = 2
    dao.create({'ip': '10.0.0.2'})
    results = dao.find_all()
    assert len(results) == 1
    assert results[0]['ip'] == '10.0.0.2'
    g.active_engagement_id = 1
    results = dao.find_all()
    assert len(results) == 1
    assert results[0]['ip'] == '10.0.0.1'
```

## Parser Unit Tests

Parsers (see the **xml-parsing** skill) follow a `validate` + `parse` pattern. Each parser extends `BaseToolParser`.

### Pattern: Parser Test Class

```python
import os
from utils.parsers.nmap_parser import NmapToolParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
SAMPLE_NMAP_XML = os.path.join(FIXTURES_DIR, 'sample_nmap.xml')

class TestNmapToolParser:
    def setup_method(self):
        self.parser = NmapToolParser()

    def test_validate_accepts_valid_xml(self):
        assert self.parser.validate(SAMPLE_NMAP_XML) is True

    def test_parse_extracts_hosts(self):
        result = self.parser.parse(SAMPLE_NMAP_XML)
        hosts = result['metadata']['hosts']
        assert len(hosts) >= 1
        assert hosts[0]['ip'] == '192.168.1.10'

    def test_parse_extracts_open_ports(self):
        result = self.parser.parse(SAMPLE_NMAP_XML)
        ports = result['metadata']['hosts'][0]['ports']
        open_ports = [p for p in ports if p['state'] == 'open']
        assert len(open_ports) == 2
```

### Testing Invalid Input

```python
def test_validate_rejects_non_nmap_xml(self, tmp_path):
    bad_file = tmp_path / "not_nmap.xml"
    bad_file.write_text('<?xml version="1.0"?><notNmap><data/></notNmap>')
    assert self.parser.validate(str(bad_file)) is False

def test_validate_rejects_malformed_xml(self, tmp_path):
    bad_file = tmp_path / "broken.xml"
    bad_file.write_text('<unclosed><tag>')
    assert self.parser.validate(str(bad_file)) is False
```

## Utility Function Tests

For pure functions without Flask dependencies, test directly.

```python
from utils.parsers.base_parser import BaseToolParser

def test_normalize_severity():
    assert BaseToolParser.normalize_severity('critical') == 'critical'
    assert BaseToolParser.normalize_severity('4') == 'critical'
    assert BaseToolParser.normalize_severity('High') == 'high'
    assert BaseToolParser.normalize_severity(None) == 'info'
```

## WARNING: Testing Against Production Schema

**The Problem:**

```python
# BAD - Hardcoded minimal schema that drifts from real schema
conn.execute('CREATE TABLE hosts (id INTEGER PRIMARY KEY, ip TEXT)')
```

**Why This Breaks:** Tests pass but real code fails because the test schema is missing columns, triggers, or FTS tables that the production `schema.sql` defines. You get false confidence.

**The Fix:**

```python
# GOOD - Load the actual schema for integration-level DAO tests
def apply_real_schema(conn):
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
```

Use minimal schemas only when testing a specific function that touches 1-2 columns. For DAO tests, prefer the real schema.

## Parametrized Tests

Use `@pytest.mark.parametrize` when testing the same logic with multiple inputs.

```python
@pytest.mark.parametrize('severity,expected_count', [
    ('critical', 1),
    ('medium', 1),
    ('low', 0),
    (None, 2),
])
def test_findings_by_severity(test_db, sample_engagement, severity, expected_count):
    populator = ReportAutoPopulator(test_db, sample_engagement)
    findings = populator.populate_findings_list(severity=severity)
    assert findings.count('## ') == expected_count
```

### WARNING: Skipping Error Case Tests

**The Problem:** Only testing happy paths. Parser crashes on malformed input in production.

**Why This Breaks:** Security tools produce inconsistent output. Nmap with `-oX` on interrupted scans, Nessus exports with missing fields, Burp with truncated XML. If you only test with clean fixture files, production data will crash your parser.

**The Fix:** Always include tests for: empty input, malformed XML/JSON, missing required fields, unexpected types.

```python
def test_parse_handles_missing_optional_fields(self, tmp_path):
    minimal = tmp_path / "minimal.xml"
    minimal.write_text('<?xml version="1.0"?><nmaprun scanner="nmap"><host><address addr="10.0.0.1" addrtype="ipv4"/><status state="up"/></host></nmaprun>')
    result = self.parser.parse(str(minimal))
    assert result['metadata']['hosts'][0]['ip'] == '10.0.0.1'
```

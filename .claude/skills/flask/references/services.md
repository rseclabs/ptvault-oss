# Services Reference

## Contents
- Architecture Overview
- DAO Layer
- Parser Services
- Helper Functions
- Utility Modules
- Anti-Patterns

## Architecture Overview

PTVault uses two service patterns:

1. **DAO classes** in `models/dao/` — CRUD operations on database tables, extending `BaseDAO`
2. **Utility functions** in `utils/` — stateless helpers for parsing, extraction, file handling

Routes call DAOs for database operations and utilities for business logic. No formal service layer class exists.

## DAO Layer

All DAOs extend `BaseDAO` in `models/dao/base.py`. The base class provides `find_all`, `find_by_id`, `create`, `update`, `delete`, and `count` with automatic engagement-scoped filtering.

```python
# models/dao/host_dao.py
from models.dao.base import BaseDAO

class HostDAO(BaseDAO):
    def __init__(self):
        super().__init__('hosts', engagement_scoped=True)

    def find_by_ip(self, ip):
        return self.find_one({'ip': ip})

    def find_with_ports(self, host_id):
        host = self.find_by_id(host_id)
        if not host:
            return None
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM host_ports WHERE host_id = ?', (host_id,))
        host['ports'] = [dict(row) for row in cursor.fetchall()]
        return host
```

### Using DAOs in Routes

```python
from models.dao.host_dao import HostDAO

@bp.route('/<int:host_id>', methods=['GET'])
@require_auth
@handle_errors
def get_host(host_id):
    dao = HostDAO()
    host = dao.find_by_id(host_id)
    if not host:
        raise NotFoundError('host', host_id)
    return jsonify(host), 200
```

### BaseDAO Key Methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `find_all` | `(filters={}, order_by='id', limit=None)` | `List[dict]` |
| `find_by_id` | `(record_id)` | `dict \| None` |
| `find_one` | `(filters)` | `dict \| None` |
| `create` | `(data)` | `int` (new ID) |
| `update` | `(record_id, data)` | `bool` |
| `delete` | `(record_id)` | `bool` |
| `count` | `(filters={})` | `int` |
| `exists` | `(filters)` | `bool` |

The `engagement_scoped=True` flag automatically adds `engagement_id = ?` to all WHERE clauses using `g.active_engagement_id`.

## Parser Services

Tool output parsers live in `utils/parsers/` with a registry for auto-discovery. See the **xml-parsing** skill for details.

```python
# utils/parsers/registry.py - auto-routes files to correct parser
from utils.parsers.nmap_parser import NmapToolParser
from utils.parsers.burp_parser import BurpToolParser
from utils.parsers.nessus_parser import NessusToolParser

PARSERS = {
    'nmap': NmapToolParser(),
    'burp': BurpToolParser(),
    'nessus': NessusToolParser(),
}
```

Each parser extends `BaseParser` and implements `parse(file_path)` returning structured metadata.

## Helper Functions

### Host Extraction (UPSERT Pattern)

From `utils/host_extractor.py`:

```python
def get_or_create_host(engagement_id, ip, hostname=None, os=None, conn=None):
    """Get existing host or create new one. Thread-safe via ON CONFLICT."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO hosts (engagement_id, ip, hostname, os)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(engagement_id, ip) DO UPDATE SET
            hostname = COALESCE(excluded.hostname, hosts.hostname),
            os = COALESCE(excluded.os, hosts.os),
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
    ''', (engagement_id, ip, hostname, os))
    return cursor.fetchone()[0]
```

### Validation Helpers

From `routes/engagements.py:16-49` — inline helpers in route files:

```python
def validate_email(email):
    if not email:
        return True  # Optional field
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_date(date_str):
    if not date_str:
        return True
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def normalize_tags(tags):
    if not tags:
        return None
    if isinstance(tags, list):
        return ','.join(str(tag).strip() for tag in tags if tag)
    return tags
```

### File Helpers

From `utils/file_helpers.py`:

```python
def sanitize_filename(filename):
    """Remove path separators and null bytes."""
    safe = re.sub(r'[/\\:\x00]', '', filename)
    return safe[:255]

def allowed_file(filename, extensions):
    ext = os.path.splitext(filename)[1].lower()
    return ext in extensions

def create_safe_filepath(engagement_id, evidence_id, filename):
    safe_name = sanitize_filename(filename)
    return f"{engagement_id}/{evidence_id}_{safe_name}"
```

## Utility Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `atomics_downloader.py` | `utils/` | Download Atomic Red Team from GitHub |
| `atomics_parser.py` | `utils/` | Parse Atomics YAML test definitions |
| `navigator_parser.py` | `utils/` | MITRE ATT&CK Navigator layer parsing |
| `markdown_export.py` | `utils/` | Generate Markdown reports from engagement data |
| `pdf_generator.py` | `utils/` | PDF generation via WeasyPrint |
| `template_renderer.py` | `utils/` | Report template rendering |
| `report_auto_populator.py` | `utils/` | Auto-fill reports from engagement findings |
| `script_generator.py` | `utils/` | Generate Bash/PowerShell test scripts |
| `audit_logger.py` | `utils/` | Audit trail for security compliance |
| `attack_map_svg.py` | `utils/` | SVG generation for attack maps |

## WARNING: Anti-Patterns

### Don't Put Business Logic in Routes

**The Problem:**

```python
# BAD - 200 lines of parsing inline in route handler
@bp.route('/import', methods=['POST'])
@require_auth
def import_scan():
    file = request.files['file']
    tree = ET.parse(file)
    root = tree.getroot()
    hosts = []
    for host_elem in root.findall('.//host'):
        # ... 150 lines of parsing ...
    # ... 50 lines of database inserts ...
```

**Why This Breaks:** Untestable. You can't unit-test the parsing without spinning up a Flask app. Route files grow to 1000+ lines and become hard to navigate.

**The Fix:** Move logic to utility functions or parser classes.

```python
@bp.route('/import', methods=['POST'])
@require_auth
@handle_errors
def import_scan():
    file = request.files['file']
    parser = NmapToolParser()
    result = parser.parse(file.stream)
    for host in result['hosts']:
        get_or_create_host(g.active_engagement_id, host['ip'], conn=g.db)
    g.db.commit()
    return jsonify({"imported": len(result['hosts'])}), 201
```

### Don't Duplicate Validation Logic

**The Problem:** `normalize_tags()` is defined in both `routes/engagements.py:42` and `routes/evidence.py:31` with identical implementations.

**The Fix:** Extract to a shared utility. For new code, use `utils/error_handler.py` helpers (`require_fields`, `validate_enum`) rather than defining per-route validators.

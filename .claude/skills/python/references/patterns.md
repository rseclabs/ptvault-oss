# Python Patterns Reference

## Contents
- Import Order Convention
- Flask Blueprint Structure
- Database Connection and Transactions
- Engagement Data Isolation
- DAO Pattern
- Abstract Base Class Pattern (Parsers)
- WARNING: Mutable Default Arguments
- WARNING: Missing Engagement Filter

---

## Import Order Convention

Always follow this order with blank lines between groups:

```python
# 1. Standard library
import os
import json
from datetime import datetime
from functools import wraps

# 2. Third-party packages
from flask import Blueprint, request, jsonify, g
from argon2 import PasswordHasher

# 3. Local application imports
from config import Config
from models.database import get_db_connection
from middleware.auth import require_auth
```

---

## Flask Blueprint Structure

### DO: Focused Blueprint with engagement guard

```python
# routes/hosts.py
hosts_bp = Blueprint('hosts', __name__, url_prefix='/api/hosts')

def require_active_engagement():
    """Get active engagement ID or return error response."""
    active_id = session.get('active_engagement_id')
    if not active_id:
        return None, (jsonify({"error": "No active engagement selected"}), 400)
    return active_id, None

@hosts_bp.route('', methods=['GET'])
@require_auth
def list_hosts():
    engagement_id, error = require_active_engagement()
    if error:
        return error
    hosts = get_hosts_for_engagement(engagement_id, g.db)
    return jsonify({"hosts": hosts}), 200
```

### DON'T: Unprotected route without engagement scope

```python
# BAD - No auth, no engagement filter, silent catch
@hosts_bp.route('/<int:host_id>')
def get_host(host_id):
    try:
        return get_any_host(host_id)  # Cross-engagement data leak!
    except:
        pass
```

**Why:** Unprotected routes bypass RBAC. Missing `engagement_id` breaks data isolation between clients. Bare except hides every error.

---

## Database Connection and Transactions

### DO: Use g.db with commit/rollback

```python
@require_auth
def create_host():
    try:
        cursor = g.db.cursor()
        cursor.execute('''
            INSERT INTO hosts (engagement_id, ip, hostname) VALUES (?, ?, ?)
        ''', (g.active_engagement_id, data['ip'], data.get('hostname')))
        g.db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 500
```

### DON'T: Create standalone connections

```python
# BAD - Orphan connection, never closed, no engagement context
def create_host():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO hosts (ip) VALUES (?)', (ip,))
    conn.commit()
```

**Why:** `g.db` is managed by `@app.teardown_appcontext` which closes it automatically. Standalone connections leak and bypass the engagement context set by `@require_auth`.

---

## Engagement Data Isolation

Every query MUST filter by `engagement_id`. This is the primary security boundary between client data.

```python
# Ownership check before any mutation
cursor.execute('''
    SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
''', (host_id, g.active_engagement_id))
if not cursor.fetchone():
    return jsonify({"error": "Host not found"}), 404
```

The DAO layer handles this automatically when `engagement_scoped=True` (default).

---

## DAO Pattern

BaseDAO in `models/dao/base.py` provides CRUD with automatic engagement scoping:

```python
class HostDAO(BaseDAO):
    def __init__(self):
        super().__init__('hosts', engagement_scoped=True)

    def find_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        return self.find_one({'ip': ip})

    def get_with_evidence_count(self) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT h.*, COUNT(DISTINCT eh.evidence_id) as evidence_count
            FROM hosts h
            LEFT JOIN evidence_hosts eh ON h.id = eh.host_id
            WHERE h.engagement_id = ?
            GROUP BY h.id ORDER BY h.ip
        ''', (self.engagement_id,))
        return [self._row_to_dict(row) for row in cursor.fetchall()]
```

**Key:** `self.db` reads from `g.db`, `self.engagement_id` reads from `g.active_engagement_id`. Both require `@require_auth`.

---

## Abstract Base Class Pattern (Parsers)

All 11 tool parsers extend `BaseToolParser`:

```python
from abc import ABC, abstractmethod

class BaseToolParser(ABC):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tool_name = self.__class__.__name__.replace('Parser', '').replace('Tool', '')

    @abstractmethod
    def validate(self, file_path: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        pass

    def normalize_severity(self, severity: str) -> str:
        """Map vendor severity strings to: critical, high, medium, low, info."""
        mapping = {'4': 'critical', '3': 'high', '2': 'medium', '1': 'low', '0': 'info'}
        return mapping.get(severity.lower(), 'medium')

    def safe_text(self, element, default: str = "") -> str:
        if element is None:
            return default
        return element.text if element.text else default
```

Parser registry auto-detects tool type. See the **xml-parsing** skill for parser implementation details.

---

## WARNING: Mutable Default Arguments

**The Problem:**

```python
# BAD - Shared mutable default across all calls
def add_tags(tags=[]):
    tags.append("new")
    return tags

add_tags()  # ['new']
add_tags()  # ['new', 'new'] - BUG!
```

**Why This Breaks:**
1. Default list created once at function definition, shared across all calls
2. Silently corrupts data in production under concurrent requests
3. Extremely hard to debug - works in unit tests, fails in real usage

**The Fix:**

```python
# GOOD
def add_tags(tags=None):
    if tags is None:
        tags = []
    tags.append("new")
    return tags
```

---

## WARNING: Missing Engagement Filter

**The Problem:**

```python
# BAD - Returns ALL hosts across ALL clients
cursor.execute('SELECT * FROM hosts WHERE ip = ?', (ip,))
```

**Why This Breaks:**
1. Client A sees Client B's confidential penetration test data
2. Violates data isolation - the core security guarantee of PTVault
3. Could constitute a data breach under NDA terms

**The Fix:**

```python
# GOOD - Always scope to active engagement
cursor.execute('SELECT * FROM hosts WHERE ip = ? AND engagement_id = ?',
               (ip, g.active_engagement_id))
```

**When You Might Be Tempted:**
- Quick lookups that "only need one field"
- Admin endpoints that seem cross-engagement
- Migration scripts running outside request context

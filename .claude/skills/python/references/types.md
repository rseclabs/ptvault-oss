# Python Types Reference

## Contents
- Type Hints in PTVault
- Common Return Types
- Database Row Conversion
- Configuration Class Pattern
- DAO Type Signatures
- WARNING: Mutable Default Arguments
- WARNING: Using `is` for Value Comparison

---

## Type Hints in PTVault

PTVault uses `typing` module hints for function signatures. Not enforced at runtime, but required for new code clarity.

```python
from typing import Optional, List, Dict, Any, Tuple

def verify_session_token(token: str) -> Optional[dict]:
    """Return payload dict if valid, None if expired/invalid."""
    try:
        return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
    except JWTError:
        return None

def hash_password(password: str) -> str:
    """Return Argon2id hash string."""
    return ph.hash(password)
```

---

## Common Return Types

| Function Pattern | Return Type | Example |
|-----------------|-------------|---------|
| Create/Insert route | `tuple[Response, int]` | `return jsonify(data), 201` |
| Read/Update route | `tuple[Response, int]` | `return jsonify(data), 200` |
| Delete route | `tuple[str, int]` | `return '', 204` |
| Error response | `tuple[Response, int]` | `return jsonify({"error": "..."}), 4xx` |
| Parser success | `Optional[Dict]` | `return {"tool": "nmap", "hosts": [...]}` |
| Parser failure | `None` | `return None` |
| DAO find_by_id | `Optional[Dict[str, Any]]` | `return dict(row) or None` |
| DAO find_all | `List[Dict[str, Any]]` | `return [dict(r) for r in rows]` |
| DAO create | `int` | `return cursor.lastrowid` |
| DAO update/delete | `bool` | `return cursor.rowcount > 0` |

---

## Database Row Conversion

SQLite `Row` objects support dict-like access when `conn.row_factory = sqlite3.Row` (set in `get_db_connection`).

### Using sqlite3.Row (preferred)

```python
cursor.execute('SELECT * FROM hosts WHERE id = ?', (host_id,))
row = cursor.fetchone()
if row:
    host = dict(row)  # Converts Row to dict with column names as keys
```

### Manual mapping (legacy pattern, avoid in new code)

```python
# Only use when you need explicit field control or bool conversion
host = {
    "id": row[0],
    "ip": row[1],
    "rooted": bool(row[4]),     # INTEGER 0/1 → Python bool
    "shell": bool(row[5]),
}
```

### BaseDAO row conversion

```python
# models/dao/base.py
def _row_to_dict(self, row) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)
```

---

## Configuration Class Pattern

`config.py` uses class attributes with env var fallbacks:

```python
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    DATABASE_PATH = os.environ.get('DATABASE_PATH', './data/ptvault.db')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or \
        base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
    JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', 24))
    MAX_FILE_SIZE = 250 * 1024 * 1024  # 250 MB
    ALLOWED_EXTENSIONS = {'.txt', '.xml', '.json', '.png', '.jpg', '.jpeg',
                          '.pdf', '.html', '.log', '.pcap', '.nessus'}
```

Access via `Config.ATTRIBUTE`:

```python
from config import Config
if file_size > Config.MAX_FILE_SIZE:
    return jsonify({"error": "File too large"}), 400
```

---

## DAO Type Signatures

BaseDAO methods use consistent type signatures:

```python
class BaseDAO:
    def __init__(self, table_name: str, engagement_scoped: bool = True): ...

    def find_all(self, filters: Optional[Dict[str, Any]] = None,
                 order_by: str = "id",
                 limit: Optional[int] = None,
                 offset: int = 0) -> List[Dict[str, Any]]: ...

    def find_by_id(self, record_id: int) -> Optional[Dict[str, Any]]: ...
    def find_one(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]: ...
    def create(self, data: Dict[str, Any]) -> int: ...
    def update(self, record_id: int, data: Dict[str, Any]) -> bool: ...
    def delete(self, record_id: int) -> bool: ...
```

Custom DAO methods follow the same patterns:

```python
class HostDAO(BaseDAO):
    def find_by_ip(self, ip: str) -> Optional[Dict[str, Any]]: ...
    def find_by_indicator(self, indicator: str, value: bool = True) -> List[Dict[str, Any]]: ...
    def find_by_color(self, color: str) -> List[Dict[str, Any]]: ...
```

---

## WARNING: Mutable Default Arguments

```python
# BAD - Shared state across calls
def build_where(filters: Dict[str, Any], extras=[]):
    extras.append("1=1")  # Grows on every call!
    return extras

# GOOD
def build_where(filters: Dict[str, Any], extras=None):
    extras = extras or []
    extras.append("1=1")
    return extras
```

Also applies to dict defaults: `options=None` then `options = options or {}`.

---

## WARNING: Using `is` for Value Comparison

```python
# BAD - Identity check, not equality
if status is 'active':  # Works by accident with string interning, breaks unpredictably

# GOOD - Value equality
if status == 'active':

# CORRECT use of `is` - only for singletons
if result is None:
if value is True:  # Only when you literally need identity check
```

**Why:** `is` checks object identity (same memory address). Python interns small integers and some strings, so `is` appears to work until it doesn't. Use `==` for values, `is` only for `None`/`True`/`False`.

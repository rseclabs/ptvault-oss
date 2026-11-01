# Python Error Handling Reference

## Contents
- API Error Response Format
- Custom Exception Hierarchy
- @handle_errors Decorator
- Database Error Handling
- Parser Error Handling
- Validation Patterns
- WARNING: Bare Except Clauses
- WARNING: Exposing Internal Errors to Clients

---

## API Error Response Format

All API errors use `{"error": "message"}` with appropriate HTTP status:

```python
return jsonify({"error": "title is required"}), 400          # Validation
return jsonify({"error": "unauthorized"}), 401                # Auth failure
return jsonify({"error": "insufficient permissions"}), 403    # RBAC denial
return jsonify({"error": "Host not found"}), 404              # Missing resource
return jsonify({"error": "Host with this IP already exists", "host_id": 5}), 409  # Conflict
return jsonify({"error": str(e)}), 500                        # Server error (dev only)
```

---

## Custom Exception Hierarchy

`utils/error_handler.py` provides structured exceptions:

```python
class PTVaultError(Exception):
    def __init__(self, message, status_code=500, details=None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self):
        return {'error': self.message, 'type': self.__class__.__name__}

class ValidationError(PTVaultError):
    def __init__(self, message, field=None, details=None):
        details = details or {}
        if field:
            details['field'] = field
        super().__init__(message, status_code=400, details=details)

class NotFoundError(PTVaultError):
    def __init__(self, resource_type, resource_id=None):
        message = f"{resource_type.capitalize()} not found"
        super().__init__(message, status_code=404)

class AuthenticationError(PTVaultError):
    def __init__(self, message="Authentication failed"):
        super().__init__(message, status_code=401)

class DatabaseError(PTVaultError):
    def __init__(self, message, query=None):
        super().__init__(message, status_code=500)
```

---

## @handle_errors Decorator

Wraps route functions for automatic error handling:

```python
from utils.error_handler import handle_errors, ValidationError, require_fields

@evidence_bp.route('', methods=['POST'])
@require_auth
@handle_errors
def create_evidence():
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required")

    require_fields(data, ['title', 'evidence_type'])
    validate_enum(data['evidence_type'], VALID_TYPES, 'evidence_type')
    # ... business logic
```

The decorator catches `PTVaultError` subclasses and returns their `status_code`. Unexpected exceptions return 500 with traceback in development, generic message in production.

---

## Database Error Handling

### Transaction pattern (standard)

```python
try:
    cursor = g.db.cursor()
    cursor.execute('INSERT INTO hosts (...) VALUES (...)', params)
    g.db.commit()
    return jsonify({"id": cursor.lastrowid}), 201
except Exception as e:
    g.db.rollback()  # ALWAYS rollback on failure
    return jsonify({"error": str(e)}), 500
```

### Handling unique constraint violations

```python
try:
    cursor.execute('INSERT INTO host_ports (...) VALUES (...)', params)
    g.db.commit()
except Exception as e:
    if 'UNIQUE constraint failed' in str(e):
        return jsonify({"error": "Port already exists for this host"}), 409
    g.db.rollback()
    return jsonify({"error": str(e)}), 500
```

### Migration safety (idempotent operations)

```python
# Always use IF NOT EXISTS for tables
cursor.execute('CREATE TABLE IF NOT EXISTS new_table (...)')

# Check column existence before ALTER
cursor.execute("SELECT name FROM pragma_table_info('hosts')")
existing = {row[0] for row in cursor.fetchall()}
if 'new_column' not in existing:
    cursor.execute('ALTER TABLE hosts ADD COLUMN new_column TEXT')
```

See the **sqlite** skill for migration patterns.

---

## Parser Error Handling

Parsers NEVER raise exceptions to callers. Return `None` on failure:

```python
class NmapToolParser(BaseToolParser):
    def parse(self, file_path=None):
        try:
            nmap_report = NmapParser.parse_fromfile(file_path or self.file_path)
            return self._extract_metadata(nmap_report)
        except NmapParserException as e:
            logger.error(f"Nmap parser error for {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing {file_path}: {e}")
            return None
```

**Why:** Parser failures are expected (malformed uploads, wrong tool type). Crashing the request is worse than returning `None` and letting the route handle it gracefully.

---

## Validation Patterns

### Field presence validation

```python
from utils.error_handler import require_fields, validate_enum

VALID_EVIDENCE_TYPES = ['note', 'command_output', 'screenshot', 'tool_output', 'other']

data = request.get_json()
require_fields(data, ['title', 'evidence_type'])
validate_enum(data['evidence_type'], VALID_EVIDENCE_TYPES, 'evidence_type')
```

### JSON metadata validation

```python
metadata = data.get('metadata')
if metadata:
    try:
        json.loads(metadata) if isinstance(metadata, str) else json.dumps(metadata)
    except json.JSONDecodeError:
        return jsonify({"error": "metadata must be valid JSON"}), 400
```

### File upload validation

```python
from config import Config

ext = os.path.splitext(filename)[1].lower()
if ext not in Config.ALLOWED_EXTENSIONS:
    return jsonify({"error": f"File type not allowed"}), 400

uploaded_file.seek(0, os.SEEK_END)
file_size = uploaded_file.tell()
uploaded_file.seek(0)
if file_size > Config.MAX_FILE_SIZE:
    return jsonify({"error": "File exceeds 250 MB limit"}), 400
```

---

## WARNING: Bare Except Clauses

**The Problem:**

```python
# BAD - Catches KeyboardInterrupt, SystemExit, everything
try:
    do_something()
except:
    pass
```

**Why This Breaks:**
1. `KeyboardInterrupt` caught - can't Ctrl+C to stop the server
2. `SystemExit` caught - can't shut down gracefully
3. All bugs hidden - you'll never find the root cause

**The Fix:**

```python
# GOOD - Catch specific exceptions
try:
    cursor.execute('ALTER TABLE hosts ADD COLUMN new_col TEXT')
except sqlite3.OperationalError:
    pass  # Column already exists - expected

# GOOD - Catch Exception (excludes KeyboardInterrupt, SystemExit)
try:
    result = parser.parse(file_path)
except Exception as e:
    logger.error(f"Parse failed: {e}")
    return None
```

---

## WARNING: Exposing Internal Errors to Clients

**The Problem:**

```python
# BAD - Leaks SQL structure, table names, column names to client
except Exception as e:
    return jsonify({"error": str(e)}), 500
    # Could expose: "no such column: hosts.secret_field"
```

**Why This Breaks:**
1. Reveals database schema to attackers
2. Exposes file paths and internal structure
3. May leak sensitive data from error messages

**The Fix:**

```python
# GOOD - Generic message in production, details in dev
except Exception as e:
    logger.error(f"Database error: {e}")
    if Config.ENVIRONMENT == 'development':
        return jsonify({"error": str(e)}), 500
    return jsonify({"error": "Internal server error"}), 500
```

The `@handle_errors` decorator handles this automatically.

---

## Validation Workflow Checklist

Copy when implementing a new endpoint:

```
- [ ] Required fields checked (return 400 if missing)
- [ ] Field values validated (enums, formats, ranges)
- [ ] JSON metadata validated if accepted
- [ ] File extension validated against ALLOWED_EXTENSIONS
- [ ] File size validated against MAX_FILE_SIZE
- [ ] Engagement ownership verified (return 404 if not owned)
- [ ] Unique constraints handled (return 409 on duplicate)
- [ ] Transaction rollback on any database error
```

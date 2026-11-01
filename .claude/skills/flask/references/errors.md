# Errors Reference

## Contents
- Error Handling Architecture
- Custom Exception Classes
- @handle_errors Decorator
- Validation Helpers
- Legacy Pattern vs Preferred Pattern
- Anti-Patterns

## Error Handling Architecture

PTVault has two error handling patterns:

1. **Preferred:** `@handle_errors` decorator with custom exceptions from `utils/error_handler.py`
2. **Legacy:** Inline try/except with manual `jsonify({"error": ...})` responses

New routes SHOULD use the preferred pattern. Existing legacy routes work fine — don't refactor them just to match.

## Custom Exception Classes

All inherit from `PTVaultError` (`utils/error_handler.py:24-46`):

```
PTVaultError (base, 500)
├── ValidationError (400)     — Bad input, missing fields
├── AuthenticationError (401) — Invalid credentials, expired token
├── AuthorizationError (403)  — Insufficient permissions
├── NotFoundError (404)       — Resource doesn't exist
├── ConflictError (409)       — Duplicate resource
├── FileUploadError (400)     — Upload failures
├── ParsingError (400)        — Tool output parsing failures
└── DatabaseError (500)       — Database operation failures
```

### Usage Examples

```python
from utils.error_handler import (
    ValidationError, NotFoundError, ConflictError,
    FileUploadError, ParsingError, DatabaseError,
    require_fields, validate_enum
)

# Validation
raise ValidationError("Password must be at least 8 characters", field='master_password')

# Not found with resource context
raise NotFoundError('host', host_id)  # "Host not found: 42"

# Conflict
raise ConflictError("User already exists")

# File upload
raise FileUploadError("File type not allowed", filename='exploit.exe')

# Parsing
raise ParsingError("Invalid Nmap XML format", tool_type='nmap')

# Database
raise DatabaseError("Failed to insert host", details={'original_error': str(e)})
```

## @handle_errors Decorator

From `utils/error_handler.py:230-288`. Catches exceptions and returns standardized JSON responses.

```python
@bp.route('/endpoint', methods=['POST'])
@require_auth
@handle_errors
def my_route():
    data = request.get_json()
    require_fields(data, ['name', 'type'])  # Raises ValidationError if missing
    validate_enum(data['type'], ['a', 'b', 'c'], 'type')  # Raises ValidationError

    cursor = g.db.cursor()
    cursor.execute('INSERT INTO items (name) VALUES (?)', (data['name'],))
    g.db.commit()
    return jsonify({"id": cursor.lastrowid}), 201
    # If anything raises, @handle_errors catches it and returns proper JSON error
```

### What @handle_errors Does

1. **PTVaultError** → Logs with context, returns `{"error": msg, "type": "ClassName"}` with correct status
2. **HTTPException** (404, 405) → Returns `{"error": description}` with HTTP status
3. **Unexpected Exception** → In development: returns traceback. In production: returns `{"error": "Internal server error"}`

### Response Format

```json
// PTVaultError response
{"error": "Password must be at least 8 characters", "type": "ValidationError"}

// Production 500 response
{"error": "Internal server error", "type": "InternalError"}

// Development 500 response (includes debug info)
{"error": "Internal server error", "type": "TypeError", "message": "...", "traceback": "..."}
```

## Validation Helpers

### require_fields

From `utils/error_handler.py:330-351`:

```python
data = request.get_json()
require_fields(data, ['name', 'client', 'status'])
# Raises ValidationError("Missing required field: name") if 'name' is missing, None, or ''
```

### validate_enum

From `utils/error_handler.py:354-374`:

```python
validate_enum(data['status'], ['active', 'completed', 'archived'], 'status')
# Raises ValidationError("Invalid status: must be one of active, completed, archived")
```

### validate_engagement_access

From `utils/error_handler.py:377-398`:

```python
engagement = validate_engagement_access(cursor, engagement_id)
# Raises NotFoundError('engagement', engagement_id) if not found
```

### safe_db_operation

From `utils/error_handler.py:295-323`:

```python
def insert_host():
    cursor.execute('INSERT INTO hosts ...', (data,))
    return cursor.lastrowid

host_id = safe_db_operation(insert_host, "Failed to insert host")
# Wraps operation in try/except, re-raises as DatabaseError
```

## Legacy Pattern vs Preferred Pattern

### Legacy (routes/hosts.py style)

```python
@bp.route('', methods=['POST'])
@require_auth
def create_item():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = data.get('name')
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        cursor = g.db.cursor()
        cursor.execute('INSERT INTO items (name) VALUES (?)', (name,))
        g.db.commit()
        return jsonify({"id": cursor.lastrowid}), 201
    except Exception as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 500
```

### Preferred (routes/auth.py style)

```python
@bp.route('', methods=['POST'])
@require_auth
@handle_errors
def create_item():
    data = request.get_json()
    require_fields(data, ['name'])

    cursor = g.db.cursor()
    cursor.execute('INSERT INTO items (name) VALUES (?)', (data['name'],))
    g.db.commit()
    return jsonify({"id": cursor.lastrowid}), 201
```

**Benefits of preferred pattern:**
- Less boilerplate (no try/except, no manual error responses)
- Consistent error format across all routes
- Automatic logging with request context
- Development vs production error detail control

## WARNING: Anti-Patterns

### Don't Expose Internal Errors in Production

**The Problem:**

```python
except Exception as e:
    return jsonify({"error": str(e)}), 500
```

**Why This Breaks:** `str(e)` can contain SQL queries, file paths, or stack traces that reveal internal architecture to attackers. PTVault uses this pattern in development for debugging convenience.

**The Fix:** Use `@handle_errors` which automatically hides details in production:

```python
# In production, returns: {"error": "Internal server error"}
# In development, returns full traceback
```

### Don't Catch Exceptions Without Rollback

**The Problem:**

```python
try:
    cursor.execute('INSERT INTO items ...', (a,))
    cursor.execute('INSERT INTO related ...', (b,))  # Fails!
    g.db.commit()
except:
    return jsonify({"error": "failed"}), 500
    # First INSERT is now in a partial transaction state
```

**Why This Breaks:** SQLite's autocommit is off when you call `cursor.execute()`. Without explicit `rollback()`, the partial transaction may persist until connection close, causing lock contention.

**The Fix:**

```python
except Exception as e:
    g.db.rollback()
    return jsonify({"error": str(e)}), 500
```

### Don't Swallow Specific Exceptions as Generic

**The Problem:**

```python
except Exception as e:
    return jsonify({"error": "Something went wrong"}), 500
```

**Why This Breaks:** A `UNIQUE constraint failed` (409) gets reported as a 500. The frontend can't distinguish between "duplicate entry" and "database crashed."

**The Fix:** Handle known exceptions specifically:

```python
except Exception as e:
    if 'UNIQUE constraint failed' in str(e):
        return jsonify({"error": "Item already exists"}), 409
    g.db.rollback()
    raise DatabaseError("Failed to create item", details={'original_error': str(e)})
```

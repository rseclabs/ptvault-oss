# PTVault Error Handling System

## Overview

PTVault uses a centralized error handling system that provides:

- **Custom exception classes** with specific error types
- **@handle_errors decorator** for automatic exception handling in routes
- **Standardized JSON error responses** with proper HTTP status codes
- **Comprehensive logging** with stack traces
- **Security**: No sensitive data exposed to clients

## Quick Start

### Basic Usage in Routes

```python
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from utils.error_handler import (
    handle_errors,
    ValidationError,
    DatabaseError,
    require_fields
)

my_bp = Blueprint('my_feature', __name__, url_prefix='/api/my-feature')

@my_bp.route('/', methods=['POST'])
@require_auth
@handle_errors  # Add this decorator to all routes
def create_item():
    # Validate request data
    data = request.get_json()
    require_fields(data, ['name', 'description'])

    # Perform database operation
    try:
        cursor = g.db.cursor()
        cursor.execute('INSERT INTO items ...', (data['name'],))
        g.db.commit()
        return jsonify({'id': cursor.lastrowid}), 201
    except Exception as e:
        raise DatabaseError("Failed to create item", details={'original_error': str(e)})
```

## Exception Classes

### Base Exception

#### PTVaultError
Base class for all PTVault exceptions.

```python
raise PTVaultError("Something went wrong", status_code=500)
```

**Properties:**
- `message`: Error message
- `status_code`: HTTP status code (default: 500)
- `details`: Dictionary of additional details (not exposed to client)

**Methods:**
- `to_dict()`: Returns JSON-serializable dict

---

### Validation Errors (400)

#### ValidationError
Raised when request data validation fails.

```python
# Simple validation error
raise ValidationError("Invalid email format")

# With field name
raise ValidationError("Email is required", field="email")

# With additional details
raise ValidationError(
    "Password too weak",
    field="password",
    details={"min_length": 8, "provided_length": 5}
)
```

**Use Cases:**
- Missing required fields
- Invalid field formats
- Data type mismatches
- Range/length violations

---

### Database Errors (500)

#### DatabaseError
Raised when database operations fail.

```python
# Simple database error
raise DatabaseError("Failed to insert record")

# With query context (for logging)
raise DatabaseError(
    "Failed to update host",
    query="UPDATE hosts SET ...",
    details={"host_id": 123}
)
```

**Use Cases:**
- Connection failures
- Query execution errors
- Transaction rollback needed
- Schema issues

---

### Authentication Errors (401)

#### AuthenticationError
Raised when authentication fails.

```python
# Default message
raise AuthenticationError()

# Custom message
raise AuthenticationError("Invalid credentials")

# With context
raise AuthenticationError(
    "Token expired",
    details={"expired_at": "2025-02-09T12:00:00"}
)
```

**Use Cases:**
- Invalid password
- Missing authentication token
- Expired JWT token
- Invalid session

---

### Authorization Errors (403)

#### AuthorizationError
Raised when user lacks permission for operation.

```python
# Default message
raise AuthorizationError()

# Custom message
raise AuthorizationError("Admin access required")

# With context
raise AuthorizationError(
    "Cannot access engagement",
    details={"engagement_id": 42, "user_id": 1}
)
```

**Use Cases:**
- Insufficient permissions
- Accessing another user's data
- Attempting privileged operation

---

### Not Found Errors (404)

#### NotFoundError
Raised when requested resource doesn't exist.

```python
# Simple not found
raise NotFoundError("engagement")

# With resource ID
raise NotFoundError("host", resource_id=123)

# With context
raise NotFoundError(
    "evidence",
    resource_id=456,
    details={"engagement_id": 10}
)
```

**Response:** `"Engagement not found: 123"`

**Use Cases:**
- Resource doesn't exist
- Invalid ID provided
- Resource was deleted

---

### Conflict Errors (409)

#### ConflictError
Raised when resource already exists or conflicts with existing data.

```python
# Duplicate resource
raise ConflictError("User already exists")

# Constraint violation
raise ConflictError(
    "Host IP already registered",
    details={"ip_address": "192.168.1.1"}
)
```

**Use Cases:**
- Duplicate records
- Unique constraint violations
- State conflicts (e.g., "engagement already archived")

---

### File Upload Errors (400)

#### FileUploadError
Raised when file upload fails.

```python
# Simple upload error
raise FileUploadError("File too large")

# With filename
raise FileUploadError(
    "Invalid file type",
    filename="document.exe",
    details={"allowed_types": [".xml", ".txt"]}
)
```

**Use Cases:**
- File size exceeds limit
- Invalid file type
- Upload I/O errors
- Filename conflicts

---

### Parsing Errors (400)

#### ParsingError
Raised when parsing tool output fails.

```python
# Simple parsing error
raise ParsingError("Invalid XML structure")

# With tool type
raise ParsingError(
    "Failed to parse Nmap output",
    tool_type="nmap",
    details={"line_number": 42}
)
```

**Use Cases:**
- Malformed XML
- Unexpected tool output format
- Missing required fields in parsed data

---

## Validation Helpers

### require_fields()
Validates that required fields are present and non-empty.

```python
from utils.error_handler import require_fields

@handle_errors
def create_engagement():
    data = request.get_json()

    # Will raise ValidationError if missing
    require_fields(data, ['name', 'client'])

    # Will raise ValidationError if empty string
    require_fields(data, ['name', 'client'], error_prefix="Engagement")
```

**Raises:** `ValidationError` with field name in details

---

### validate_enum()
Validates that value is in allowed set.

```python
from utils.error_handler import validate_enum

@handle_errors
def update_engagement():
    data = request.get_json()

    # Validate status field
    validate_enum(
        data['status'],
        ['active', 'completed', 'archived'],
        'status'
    )
```

**Raises:** `ValidationError` with allowed values in details

---

### validate_engagement_access()
Validates engagement exists and user has access.

```python
from utils.error_handler import validate_engagement_access

@handle_errors
def get_engagement_details(engagement_id):
    cursor = g.db.cursor()

    # Will raise NotFoundError if engagement doesn't exist
    engagement = validate_engagement_access(cursor, engagement_id)

    # Continue with engagement data...
```

**Raises:** `NotFoundError` if engagement doesn't exist

**Returns:** Engagement row dict

---

## @handle_errors Decorator

The `@handle_errors` decorator automatically:

1. Catches all exceptions
2. Logs with full context and stack trace
3. Returns standardized JSON responses
4. Uses appropriate HTTP status codes
5. Hides sensitive data from client

### Usage Order

Always place `@handle_errors` **after** other decorators:

```python
@my_bp.route('/')
@require_auth
@require_active_engagement
@handle_errors  # Must be last
def my_route():
    pass
```

### Error Response Format

**PTVault Errors:**
```json
{
  "error": "Engagement not found: 123",
  "type": "NotFoundError"
}
```

**Unexpected Errors (Development):**
```json
{
  "error": "Internal server error",
  "type": "ZeroDivisionError",
  "message": "division by zero",
  "traceback": "Traceback (most recent call last)..."
}
```

**Unexpected Errors (Production):**
```json
{
  "error": "Internal server error",
  "type": "InternalError"
}
```

---

## Logging

All exceptions are logged with:

- Exception class name
- Error message
- Full stack trace
- Request context (route, method, user_id, engagement_id)
- PTVault error details (if applicable)

### Log Format

```
ERROR: Exception occurred: ValidationError
Message: Invalid email format
Context: {'route': 'auth.setup', 'method': 'POST', 'path': '/api/auth/setup'}
Details: {'field': 'email'}
Traceback (most recent call last):
  ...
```

---

## Migration Guide

### Before (Old Pattern)

```python
@my_bp.route('/', methods=['POST'])
@require_auth
def create_item():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "name required"}), 400

    try:
        cursor = g.db.cursor()
        cursor.execute('INSERT INTO items ...', (data['name'],))
        g.db.commit()
        return jsonify({'id': cursor.lastrowid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

### After (New Pattern)

```python
from utils.error_handler import handle_errors, require_fields, DatabaseError

@my_bp.route('/', methods=['POST'])
@require_auth
@handle_errors
def create_item():
    data = request.get_json()
    require_fields(data, ['name'])

    try:
        cursor = g.db.cursor()
        cursor.execute('INSERT INTO items ...', (data['name'],))
        g.db.commit()
        return jsonify({'id': cursor.lastrowid}), 201
    except Exception as e:
        raise DatabaseError("Failed to create item", details={'original_error': str(e)})
```

**Benefits:**
- Cleaner code
- Consistent error responses
- Automatic logging
- Better error context

---

## Best Practices

### 1. Use Specific Exceptions

❌ **Don't:**
```python
raise Exception("Something failed")
```

✓ **Do:**
```python
raise ValidationError("Invalid email format", field="email")
```

---

### 2. Provide Context in Details

❌ **Don't:**
```python
raise DatabaseError("Query failed")
```

✓ **Do:**
```python
raise DatabaseError(
    "Failed to insert host",
    query="INSERT INTO hosts...",
    details={"host_id": 123, "original_error": str(e)}
)
```

---

### 3. Re-raise PTVault Errors

❌ **Don't:**
```python
try:
    require_fields(data, ['name'])
except ValidationError:
    return jsonify({"error": "validation failed"}), 400
```

✓ **Do:**
```python
try:
    require_fields(data, ['name'])
except ValidationError:
    raise  # Let @handle_errors handle it
```

---

### 4. Convert Generic Exceptions

❌ **Don't:**
```python
try:
    cursor.execute('INSERT ...')
except Exception as e:
    raise  # Becomes generic 500 error
```

✓ **Do:**
```python
try:
    cursor.execute('INSERT ...')
except Exception as e:
    raise DatabaseError(
        "Failed to create record",
        details={'original_error': str(e)}
    )
```

---

### 5. Use Validation Helpers

❌ **Don't:**
```python
if not data or not data.get('name'):
    raise ValidationError("name required")
if not data.get('client'):
    raise ValidationError("client required")
```

✓ **Do:**
```python
require_fields(data, ['name', 'client'])
```

---

## Examples

### Complete Route Example

```python
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth, require_active_engagement
from utils.error_handler import (
    handle_errors,
    ValidationError,
    DatabaseError,
    NotFoundError,
    require_fields,
    validate_enum
)

hosts_bp = Blueprint('hosts', __name__, url_prefix='/api/hosts')

@hosts_bp.route('/', methods=['POST'])
@require_auth
@require_active_engagement
@handle_errors
def create_host():
    """Create a new host."""
    # Parse and validate request
    data = request.get_json()
    require_fields(data, ['ip_address'])

    # Validate enum values
    if data.get('status'):
        validate_enum(
            data['status'],
            ['active', 'inactive'],
            'status'
        )

    # Database operation
    try:
        cursor = g.db.cursor()

        # Check for duplicates
        cursor.execute(
            'SELECT id FROM hosts WHERE ip_address = ? AND engagement_id = ?',
            (data['ip_address'], g.active_engagement_id)
        )
        if cursor.fetchone():
            raise ConflictError(f"Host {data['ip_address']} already exists")

        # Insert host
        cursor.execute(
            'INSERT INTO hosts (engagement_id, ip_address, hostname) VALUES (?, ?, ?)',
            (g.active_engagement_id, data['ip_address'], data.get('hostname'))
        )
        g.db.commit()

        return jsonify({
            'id': cursor.lastrowid,
            'ip_address': data['ip_address']
        }), 201

    except (ConflictError, ValidationError):
        raise  # Re-raise PTVault errors
    except Exception as e:
        raise DatabaseError(
            "Failed to create host",
            details={
                'ip_address': data['ip_address'],
                'original_error': str(e)
            }
        )


@hosts_bp.route('/<int:host_id>', methods=['GET'])
@require_auth
@require_active_engagement
@handle_errors
def get_host(host_id):
    """Get host details."""
    cursor = g.db.cursor()

    cursor.execute(
        'SELECT * FROM hosts WHERE id = ? AND engagement_id = ?',
        (host_id, g.active_engagement_id)
    )
    host = cursor.fetchone()

    if not host:
        raise NotFoundError("host", resource_id=host_id)

    return jsonify({
        'id': host[0],
        'ip_address': host[1],
        'hostname': host[2]
    })
```

---

## Testing

Run the test suite:

```bash
python3 test_error_handler.py
```

This tests:
- All exception classes
- Validation helpers
- JSON response format
- Error context

---

## Future Enhancements

Potential improvements:

1. **Error Codes**: Add numeric error codes for client-side handling
2. **i18n Support**: Localized error messages
3. **Rate Limiting**: Specific exception for rate limit violations
4. **Audit Logging**: Track security-relevant errors separately
5. **Error Metrics**: Track error frequency and types

---

## Reference

### All Exception Classes

| Exception | Status | Use Case |
|-----------|--------|----------|
| `PTVaultError` | 500 | Base class |
| `ValidationError` | 400 | Invalid request data |
| `DatabaseError` | 500 | Database operations |
| `AuthenticationError` | 401 | Login failures |
| `AuthorizationError` | 403 | Permission denied |
| `NotFoundError` | 404 | Resource not found |
| `ConflictError` | 409 | Duplicate/conflict |
| `FileUploadError` | 400 | Upload failures |
| `ParsingError` | 400 | Tool output parsing |

### All Helpers

| Helper | Purpose |
|--------|---------|
| `require_fields(data, fields)` | Validate required fields |
| `validate_enum(value, allowed, name)` | Validate enum values |
| `validate_engagement_access(cursor, id)` | Check engagement exists |
| `log_exception(exc, context)` | Log with stack trace |
| `get_error_context()` | Get request context |

---

*For questions or issues, see `/utils/error_handler.py`*

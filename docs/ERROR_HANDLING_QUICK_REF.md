# PTVault Error Handling - Quick Reference

## Import Statement

```python
from utils.error_handler import (
    handle_errors,           # Decorator for routes
    ValidationError,         # 400 - Invalid request data
    DatabaseError,          # 500 - Database failures
    AuthenticationError,    # 401 - Login failures
    AuthorizationError,     # 403 - Permission denied
    NotFoundError,          # 404 - Resource not found
    ConflictError,          # 409 - Duplicate/conflict
    FileUploadError,        # 400 - Upload failures
    ParsingError,           # 400 - Parsing failures
    require_fields,         # Helper: validate required fields
    validate_enum,          # Helper: validate enum values
)
```

## Basic Route Pattern

```python
@my_bp.route('/', methods=['POST'])
@require_auth
@handle_errors  # Always last decorator
def my_route():
    data = request.get_json()
    require_fields(data, ['name', 'description'])
    # Your logic here
```

## Exception Quick Reference

| Exception | Status | Usage |
|-----------|--------|-------|
| `ValidationError("message", field="name")` | 400 | Invalid input |
| `DatabaseError("message", query="...")` | 500 | DB failure |
| `AuthenticationError("message")` | 401 | Login failed |
| `AuthorizationError("message")` | 403 | No permission |
| `NotFoundError("resource", resource_id=123)` | 404 | Not found |
| `ConflictError("message")` | 409 | Duplicate |
| `FileUploadError("message", filename="...")` | 400 | Upload error |
| `ParsingError("message", tool_type="nmap")` | 400 | Parse error |

## Common Patterns

### Validate Required Fields
```python
data = request.get_json()
require_fields(data, ['name', 'client'])
```

### Validate Enum Values
```python
validate_enum(data['status'], ['active', 'archived'], 'status')
```

### Check Resource Exists
```python
cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
item = cursor.fetchone()
if not item:
    raise NotFoundError('item', resource_id=item_id)
```

### Database Error Handling
```python
try:
    cursor.execute('INSERT INTO items ...', (data,))
    g.db.commit()
except Exception as e:
    raise DatabaseError("Failed to create item", details={'original_error': str(e)})
```

### File Upload Validation
```python
if not allowed_file(filename):
    raise FileUploadError("Invalid file type", filename=filename)

if file.content_length > Config.MAX_FILE_SIZE:
    raise FileUploadError("File too large", filename=filename)
```

### Tool Output Parsing
```python
try:
    metadata = parser.parse(file_path)
except Exception as e:
    raise ParsingError("Failed to parse output", tool_type="nmap", details={'error': str(e)})
```

## Response Examples

### Validation Error
```json
{
  "error": "Name is required",
  "type": "ValidationError"
}
```

### Not Found
```json
{
  "error": "Engagement not found: 123",
  "type": "NotFoundError"
}
```

### Database Error
```json
{
  "error": "Failed to create host",
  "type": "DatabaseError"
}
```

## Testing

```bash
python3 test_error_handler.py
```

## Full Documentation

See `/docs/ERROR_HANDLING.md` for complete guide.

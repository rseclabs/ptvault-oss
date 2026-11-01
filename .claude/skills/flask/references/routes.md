# Routes Reference

## Contents
- Blueprint Structure
- Decorator Order
- Request Handling Patterns
- Response Conventions
- File Upload Handling
- Anti-Patterns

## Blueprint Structure

Every blueprint follows the same skeleton. Naming: `snake_case` with `_bp` suffix.

```python
# routes/feature.py
from flask import Blueprint, request, jsonify, g, session
from middleware.auth import require_auth
from utils.error_handler import handle_errors, ValidationError, require_fields

feature_bp = Blueprint('feature', __name__, url_prefix='/api/feature')
```

Registration in `app.py:97-114`:

```python
from routes.feature import feature_bp
app.register_blueprint(feature_bp)
```

## Decorator Order

Decorators execute bottom-up. `@require_auth` MUST run before anything that accesses `g.db` or `g.current_user`.

```python
# CORRECT order
@bp.route('/<int:id>', methods=['PUT'])
@require_auth                          # Runs 1st: sets g.db, g.current_user
@require_role('admin')                 # Runs 2nd: checks role
@require_engagement_access('editor')   # Runs 3rd: checks engagement membership
@handle_errors                         # Runs 4th: wraps in try/except
def update_item(id):
    ...
```

### WARNING: Reversed Decorator Order

**The Problem:**

```python
# BAD - @require_role runs before @require_auth
@bp.route('/admin')
@require_role('admin')  # g.current_user_role doesn't exist yet!
@require_auth
def admin_panel():
    ...
```

**Why This Breaks:** `@require_role` accesses `g.current_user_role`, which is set by `@require_auth`. Reversing the order causes `AttributeError` or 401 responses on every request.

**The Fix:** Always stack `@require_auth` immediately after `@bp.route()`.

## Request Handling Patterns

### GET with Query Parameters

From `routes/evidence.py` search endpoint:

```python
@bp.route('/search', methods=['GET'])
@require_auth
@handle_errors
def search_items():
    q = request.args.get('q', '')
    tags = request.args.get('tags')
    severity = request.args.get('severity')
    limit = min(int(request.args.get('limit', 50)), 500)  # Cap at 500

    query = "SELECT * FROM evidence WHERE engagement_id = ?"
    params = [g.active_engagement_id]

    if q:
        query += " AND id IN (SELECT rowid FROM evidence_fts WHERE evidence_fts MATCH ?)"
        params.append(q)
    if severity:
        query += " AND severity_level = ?"
        params.append(severity)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor = g.db.cursor()
    cursor.execute(query, params)
    return jsonify([dict(row) for row in cursor.fetchall()]), 200
```

### POST with Validation (Preferred Pattern)

```python
@bp.route('', methods=['POST'])
@require_auth
@handle_errors
def create_item():
    data = request.get_json()
    require_fields(data, ['name', 'status'])
    validate_enum(data['status'], ['active', 'completed', 'archived'], 'status')

    cursor = g.db.cursor()
    cursor.execute('INSERT INTO items (name, status, engagement_id) VALUES (?, ?, ?)',
                   (data['name'], data['status'], g.active_engagement_id))
    g.db.commit()
    return jsonify({"id": cursor.lastrowid}), 201
```

### Dynamic UPDATE (Partial Updates)

From `routes/hosts.py:240-264`:

```python
update_fields = []
update_values = []

for field in ['hostname', 'os', 'notes', 'color_category']:
    if field in data:
        update_fields.append(f"{field} = ?")
        update_values.append(data[field])

# Boolean fields stored as INTEGER
for field in ['rooted', 'shell', 'interested', 'flagged', 'reviewed']:
    if field in data:
        update_fields.append(f"{field} = ?")
        update_values.append(1 if data[field] else 0)

if not update_fields:
    return jsonify({"error": "No fields to update"}), 400

update_fields.append("updated_at = CURRENT_TIMESTAMP")
update_values.append(item_id)

query = f"UPDATE hosts SET {', '.join(update_fields)} WHERE id = ?"
cursor.execute(query, update_values)
g.db.commit()
```

## Response Conventions

| Status | When | Body |
|--------|------|------|
| 200 | GET success, PUT success | `jsonify(data)` |
| 201 | POST created | `jsonify(created_item)` |
| 204 | DELETE success | `'', 204` (empty body) |
| 400 | Bad input | `{"error": "name is required"}` |
| 401 | No/invalid auth | `{"error": "unauthorized"}` |
| 403 | Wrong role/engagement | `{"error": "insufficient permissions"}` |
| 404 | Not found | `{"error": "Host not found"}` |
| 409 | Duplicate | `{"error": "already exists", "host_id": 5}` |
| 500 | Server error | `{"error": "Internal server error"}` |

## File Upload Handling

From `routes/evidence.py` — handles both JSON and multipart:

```python
@bp.route('', methods=['POST'])
@require_auth
@handle_errors
def create_evidence():
    if request.content_type and 'multipart/form-data' in request.content_type:
        title = request.form.get('title')
        file = request.files.get('file')

        if file and file.filename:
            if not allowed_file(file.filename, Config.ALLOWED_EXTENSIONS):
                raise FileUploadError("File type not allowed", filename=file.filename)

            # Check size
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            if size > Config.MAX_FILE_SIZE:
                raise FileUploadError("File too large (max 250MB)", filename=file.filename)

            safe_path = create_safe_filepath(engagement_id, evidence_id, file.filename)
            file.save(os.path.join(Config.UPLOAD_FOLDER, safe_path))
    else:
        data = request.get_json()
        require_fields(data, ['title', 'type'])
```

## WARNING: Anti-Patterns

### Never Skip Engagement Filtering

**The Problem:**

```python
# BAD - returns data from ALL engagements
cursor.execute('SELECT * FROM hosts WHERE id = ?', (host_id,))
```

**Why This Breaks:** Violates per-engagement data isolation. A user in Engagement A can read hosts from Engagement B. This is a **security vulnerability** in a pentest tool handling sensitive client data.

**The Fix:**

```python
cursor.execute('SELECT * FROM hosts WHERE id = ? AND engagement_id = ?',
               (host_id, g.active_engagement_id))
```

### Never Build SQL with f-strings from User Input

**The Problem:**

```python
# BAD - SQL injection
sort_col = request.args.get('sort', 'name')
cursor.execute(f"SELECT * FROM items ORDER BY {sort_col}")
```

**Why This Breaks:** User sends `sort=name; DROP TABLE items--` and your data is gone.

**The Fix:** Whitelist allowed columns.

```python
ALLOWED_SORT = {'name', 'created_at', 'status'}
sort_col = request.args.get('sort', 'created_at')
if sort_col not in ALLOWED_SORT:
    sort_col = 'created_at'
cursor.execute(f"SELECT * FROM items ORDER BY {sort_col}")
```

**Note:** The dynamic `UPDATE` pattern uses f-strings for column names, but those come from a hardcoded list in the route handler, not from user input. This is safe.

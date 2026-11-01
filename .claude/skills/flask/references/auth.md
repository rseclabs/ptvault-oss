# Auth Reference

## Contents
- Authentication Flow
- Middleware Decorators
- RBAC System
- JWT Cookie Handling
- Session Management
- Security Patterns

## Authentication Flow

PTVault uses Argon2id for password hashing (see **argon2** skill) and HS256 JWT tokens in httpOnly cookies (see **jwt** skill).

### Setup (First Run) — routes/auth.py:25-94

```python
@auth_bp.route('/setup', methods=['POST'])
@handle_errors
def setup():
    data = request.get_json()
    require_fields(data, ['master_password'])

    if len(data['master_password']) < 8:
        raise ValidationError("Password must be at least 8 characters", field='master_password')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        raise ConflictError("User already exists")

    password_hash = hash_master_password(data['master_password'])
    cursor.execute('INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)',
                   (username, email, full_name, password_hash, 'admin'))
    conn.commit()

    # Auto-login after setup
    token = create_session_token(user_id, role='admin', username=username)
    response = make_response(jsonify({"status": "created", "user_id": user_id}))
    response.set_cookie('auth_token', token, httponly=True, samesite='Lax', max_age=86400)
    return response, 201
```

### Login — routes/auth.py:97-185

Supports both legacy `master_password` (single-user) and new `username`/`password` (multi-user):

```python
@auth_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    data = request.get_json()

    if 'master_password' in data:
        password = data['master_password']
        username = None
    else:
        require_fields(data, ['username', 'password'])
        username = data['username']
        password = data['password']

    # Find user, verify password, create token...
    if not verify_password(password, password_hash):
        raise AuthenticationError("Invalid credentials")

    token = create_session_token(user_id, role=role, username=db_username)
    response = make_response(jsonify({"status": "authenticated", "user_id": user_id, "role": role}))
    response.set_cookie('auth_token', token, httponly=True, secure=False, samesite='Lax', max_age=86400)
    return response, 200
```

## Middleware Decorators

### @require_auth (middleware/auth.py:155-192)

Sets up the request context. **Must be the first decorator after `@bp.route()`.**

Provides on `g`:
- `g.current_user` — user ID (int)
- `g.current_user_role` — `'admin'`, `'editor'`, or `'viewer'`
- `g.current_username` — username string
- `g.db` — SQLite connection
- `g.active_engagement_id` — from `session['active_engagement_id']` (may be None)

### @require_role (middleware/auth.py:195-225)

Restricts to specific roles. Must follow `@require_auth`.

```python
@bp.route('/users', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def create_user():
    ...  # Only admins can create users
```

Accepts multiple roles: `@require_role('admin', 'editor')`

### @require_engagement_access (middleware/auth.py:228-283)

Checks engagement-specific membership. Role hierarchy: `owner > editor > viewer`. Admins bypass all checks.

```python
@bp.route('/evidence', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_evidence():
    # g.engagement_role is set to user's role in this engagement
    ...
```

### Helper Function Pattern (Alternative)

From `routes/hosts.py:20-25` — some routes use a helper function instead of a decorator:

```python
def require_active_engagement():
    """Return (engagement_id, None) or (None, error_response)."""
    active_id = session.get('active_engagement_id')
    if not active_id:
        return None, (jsonify({"error": "No active engagement selected"}), 400)
    return active_id, None

# Usage:
@bp.route('', methods=['GET'])
@require_auth
def list_hosts():
    engagement_id, error = require_active_engagement()
    if error:
        return error
    ...
```

## RBAC System

### Role Hierarchy

| Role | Scope | Capabilities |
|------|-------|-------------|
| `admin` | Global | All operations, user management, access all engagements |
| `editor` | Engagement | Create/edit evidence, hosts, reports |
| `viewer` | Engagement | Read-only access |
| `owner` | Engagement | Full control including member management |

### Engagement Members Table

```sql
CREATE TABLE engagement_members (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    UNIQUE(engagement_id, user_id)
);
```

## JWT Cookie Handling

### Cookie Settings

```python
response.set_cookie(
    'auth_token',
    token,
    httponly=True,     # Blocks document.cookie access (XSS protection)
    secure=False,      # Set True in production with HTTPS
    samesite='Lax',    # CSRF protection
    max_age=86400      # 24 hours
)
```

### Logout

```python
@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({"status": "logged out"}))
    response.delete_cookie('auth_token')
    return response, 200
```

## Session Management

### Setting Active Engagement

```python
@engagements_bp.route('/active', methods=['POST'])
@require_auth
def set_active_engagement():
    data = request.get_json()
    engagement_id = data.get('engagement_id')

    cursor = g.db.cursor()
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    session['active_engagement_id'] = engagement_id
    return jsonify({"active_engagement_id": engagement_id}), 200
```

## Security Patterns

### Data Isolation (Critical)

EVERY query against engagement-scoped tables MUST filter by `engagement_id`:

```python
# CORRECT
cursor.execute('SELECT * FROM hosts WHERE id = ? AND engagement_id = ?',
               (host_id, g.active_engagement_id))

# WRONG - exposes data across engagements
cursor.execute('SELECT * FROM hosts WHERE id = ?', (host_id,))
```

### Ownership Verification for Nested Resources

From `routes/hosts.py:350-365`:

```python
# Verify host belongs to engagement
cursor.execute('SELECT id FROM hosts WHERE id = ? AND engagement_id = ?',
               (host_id, engagement_id))
if not cursor.fetchone():
    return jsonify({"error": "Host not found"}), 404

# Verify evidence belongs to same engagement
cursor.execute('SELECT id FROM evidence WHERE id = ? AND engagement_id = ?',
               (evidence_id, engagement_id))
if not cursor.fetchone():
    return jsonify({"error": "Evidence not found"}), 404
```

### WARNING: Unprotected Routes

`/api/auth/setup`, `/api/auth/login`, `/api/auth/logout`, and `/api/health` are intentionally unauthenticated. NEVER add sensitive data to these endpoints. The setup endpoint checks `SELECT COUNT(*) FROM users` to prevent re-setup.

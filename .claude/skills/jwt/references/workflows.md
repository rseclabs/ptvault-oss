# JWT Workflows Reference

## Contents
- Login Flow
- Logout Flow
- First-Time Setup Flow
- Multi-User Login
- Frontend Integration
- Debugging Authentication
- Adding a New Protected Endpoint

## Login Flow

### Complete Login Implementation

```python
# routes/auth.py:97-185
@auth_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    data = request.get_json()

    # Support legacy master_password or new username/password
    if 'master_password' in data:
        password = data['master_password']
        username = None
    else:
        require_fields(data, ['username', 'password'])
        username = data['username']
        password = data['password']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find user by username or get first user (legacy)
    if username:
        cursor.execute('SELECT id, username, password_hash, role, is_active FROM users WHERE username = ?', (username,))
    else:
        cursor.execute('SELECT id, username, password_hash, role, is_active FROM users LIMIT 1')

    user = cursor.fetchone()
    if not user:
        raise AuthenticationError("Invalid credentials")

    user_id, db_username, password_hash, role, is_active = user

    if not is_active:
        raise AuthenticationError("Account is deactivated")

    # See the **argon2** skill for password verification
    if not verify_password(password, password_hash):
        raise AuthenticationError("Invalid credentials")

    # Create JWT and set cookie
    token = create_session_token(user_id, role=role, username=db_username)

    response = make_response(jsonify({
        "status": "authenticated",
        "user_id": user_id,
        "username": db_username,
        "role": role
    }))
    response.set_cookie('auth_token', token, httponly=True, secure=False, samesite='Lax', max_age=86400)
    return response, 200
```

### Login Checklist

Copy this checklist and track progress:
- [ ] Parse request body (support both legacy and multi-user formats)
- [ ] Query user from database by username
- [ ] Check `is_active` flag before verifying password
- [ ] Verify password with Argon2id (`verify_password()`)
- [ ] Update `last_login` timestamp
- [ ] Create JWT with `create_session_token(user_id, role, username)`
- [ ] Set httpOnly cookie in response
- [ ] Return user info (id, username, role)

## Logout Flow

```python
# routes/auth.py:188-195
@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({"status": "logged out"}))
    response.delete_cookie('auth_token')
    return response, 200
```

**Important:** JWT tokens cannot be server-side invalidated without a blacklist. `delete_cookie` only removes the client-side cookie. The token remains valid until `exp` if intercepted. For PTVault's local-first threat model, this is acceptable.

## First-Time Setup Flow

```python
# routes/auth.py:25-94
@auth_bp.route('/setup', methods=['POST'])
@handle_errors
def setup():
    data = request.get_json()
    require_fields(data, ['master_password'])

    if len(data['master_password']) < 8:
        raise ValidationError("Password must be at least 8 characters", field='master_password')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Prevent duplicate setup
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        raise ConflictError("User already exists")

    # Hash password (see the **argon2** skill)
    password_hash = hash_master_password(data['master_password'])
    cursor.execute(
        'INSERT INTO users (username, email, full_name, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, 1)',
        (data.get('username', 'admin'), data.get('email', 'admin@ptvault.local'),
         data.get('full_name', 'Administrator'), password_hash, 'admin')
    )
    conn.commit()
    user_id = cursor.lastrowid

    # Auto-login: issue JWT immediately after setup
    token = create_session_token(user_id, role='admin', username=data.get('username', 'admin'))
    response = make_response(jsonify({"status": "created", "user_id": user_id}))
    response.set_cookie('auth_token', token, httponly=True, samesite='Lax', max_age=86400)
    return response, 201
```

**Key design decision:** Setup auto-logs in the user by issuing a JWT cookie in the 201 response. The frontend redirects to `/dashboard` immediately.

## Frontend Integration

### API Layer (Cookie-Based)

```javascript
// static/js/api/auth.js
export const AuthAPI = {
    async setup(masterPassword) {
        return apiRequest.post('/auth/setup', { master_password: masterPassword });
    },
    async login(masterPassword) {
        return apiRequest.post('/auth/login', { master_password: masterPassword });
    },
    async logout() {
        return apiRequest.post('/auth/logout', {});
    }
};
```

No token management in JS — the httpOnly cookie is set by the server and sent automatically by the browser on every request. See the **javascript** skill for the `apiRequest` wrapper.

### Global 401 Handling

```javascript
// static/js/lib/request.js pattern
async function apiRequest(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = '/login';
        throw new Error('Session expired');
    }
    return response;
}
```

All API calls go through this wrapper. When any endpoint returns 401, the user is redirected to login. No token refresh logic needed.

## Debugging Authentication

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 on all requests | Missing `auth_token` cookie | Check browser DevTools > Application > Cookies |
| Token invalid after restart | Auto-generated `JWT_SECRET_KEY` changes | Set `JWT_SECRET_KEY` in `.env` |
| "unauthorized" with valid cookie | Token expired | Check `exp` claim vs current UTC time |
| 401 after deploy | Different secret key between instances | Use same `JWT_SECRET_KEY` env var |
| Cookie not sent cross-origin | Missing `credentials: 'include'` | Add to fetch options (not needed for same-origin) |

### Debug Token Contents

```python
# For debugging only — never in production
from jose import jwt

def debug_token(token: str):
    unverified = jwt.get_unverified_claims(token)
    print(f"User ID: {unverified.get('user_id')}")
    print(f"Role: {unverified.get('role')}")
    print(f"Username: {unverified.get('username')}")
    print(f"Expires: {datetime.utcfromtimestamp(unverified.get('exp'))}")
```

### Verify Cookie in Browser

Cookies are httpOnly — `document.cookie` will NOT show `auth_token` (this is correct). Use:
- Chrome: DevTools > Application > Cookies > localhost
- Firefox: DevTools > Storage > Cookies
- Check Network tab for `Cookie: auth_token=...` header on requests

## Adding a New Protected Endpoint

### Checklist

Copy this checklist and track progress:
- [ ] Create route function in appropriate `routes/*.py` file
- [ ] Add `@require_auth` decorator
- [ ] Add `@require_role()` if endpoint needs role restriction
- [ ] Add `@require_engagement_access()` if endpoint is engagement-scoped
- [ ] Access user via `g.current_user`, database via `g.db`
- [ ] Filter queries by `g.active_engagement_id` for data isolation
- [ ] Return JSON error responses with appropriate HTTP status codes
- [ ] Test with valid token, expired token, and no token

### Decorator Order

```python
# CORRECT order — decorators apply bottom-up
@bp.route('/api/resource', methods=['PUT'])
@require_auth                          # Runs first: validates JWT
@require_role('admin', 'tester')       # Runs second: checks system role
@require_engagement_access('editor')   # Runs third: checks engagement membership
def update_resource():
    pass
```

### Validation Flow

1. Add the endpoint with decorators
2. Test: `curl -b cookies.txt http://localhost:5001/api/your-endpoint`
3. If 401, check cookie file has valid `auth_token`
4. If 403, check user role matches decorator requirements
5. Only proceed when auth passes

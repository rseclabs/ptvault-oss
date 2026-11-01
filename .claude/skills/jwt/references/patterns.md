# JWT Patterns Reference

## Contents
- Token Creation
- Token Validation
- Cookie Configuration
- Route Protection Decorators
- RBAC and Engagement Access
- Anti-Patterns

## Token Creation

### Standard Token with Role Claims

```python
# models/auth.py:88-108
def create_session_token(user_id: int, role: str = 'tester', username: str = None) -> str:
    expiry = datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRY_HOURS)
    payload = {
        'user_id': user_id,
        'role': role,
        'username': username,
        'exp': expiry
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
```

**Rules:**
- Always include `exp` claim for automatic expiration
- Use `datetime.utcnow()` — `datetime.now()` causes timezone-dependent expiry bugs
- Keep payload minimal — JWT payload is base64-encoded, NOT encrypted
- Include `role` for RBAC checks in middleware without extra DB queries

## Token Validation

### Safe Decoding

```python
# models/auth.py:111-125
def verify_session_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except JWTError:
        return None
```

**Why `algorithms=['HS256']` is mandatory:** Without explicit algorithm pinning, an attacker can forge tokens using the `none` algorithm or switch to RS256 with a known public key. python-jose validates against the list you provide — always pass a single-element list matching your signing algorithm.

## Cookie Configuration

### Production-Ready Cookie Settings

```python
# routes/auth.py — pattern used in setup() and login()
response.set_cookie(
    'auth_token',
    token,
    httponly=True,      # CRITICAL: blocks document.cookie access (XSS protection)
    secure=False,       # Set True in production with HTTPS
    samesite='Lax',     # Blocks cross-origin POST requests (CSRF)
    max_age=86400       # 24 hours — must match JWT_EXPIRY_HOURS
)
```

| Setting | Dev | Production | Why |
|---------|-----|------------|-----|
| `httponly` | `True` | `True` | XSS cannot steal token via `document.cookie` |
| `secure` | `False` | `True` | Prevents token leaking over HTTP in production |
| `samesite` | `'Lax'` | `'Lax'` | Allows same-site navigations, blocks cross-origin POSTs |
| `max_age` | `86400` | `86400` | Must equal `JWT_EXPIRY_HOURS * 3600` |

### WARNING: Cookie/JWT Expiry Mismatch

**The Problem:** If `max_age` differs from JWT `exp`, users get confusing behavior — either the cookie expires before the JWT (silent logout) or the JWT expires before the cookie (401 errors with a cookie still present).

**The Fix:** Always derive `max_age` from `Config.JWT_EXPIRY_HOURS`:
```python
max_age=Config.JWT_EXPIRY_HOURS * 3600
```

## Route Protection Decorators

### @require_auth — Base Authentication

```python
# middleware/auth.py:155-192
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return jsonify({"error": "unauthorized"}), 401

        payload = verify_session_token(token)
        if not payload:
            return jsonify({"error": "unauthorized"}), 401

        g.current_user = payload.get('user_id')
        g.current_user_role = payload.get('role', 'tester')
        g.current_username = payload.get('username')
        g.db = get_db_connection()
        g.active_engagement_id = session.get('active_engagement_id')

        return f(*args, **kwargs)
    return decorated_function
```

**Provides on `g`:**
- `g.current_user` — User ID (int)
- `g.current_user_role` — Role string ('admin', 'tester', 'viewer')
- `g.current_username` — Username string
- `g.db` — SQLite connection (ready to use)
- `g.active_engagement_id` — Current engagement ID or None

### @require_role — System-Level RBAC

```python
# middleware/auth.py:195-225
@require_auth
@require_role('admin')
def admin_only():
    pass

@require_auth
@require_role('admin', 'tester')
def admin_or_tester():
    pass
```

Must come AFTER `@require_auth`. Checks `g.current_user_role` against allowed roles.

### @require_engagement_access — Engagement-Level RBAC

```python
# middleware/auth.py:228-283
@require_auth
@require_engagement_access('editor')
def update_evidence(evidence_id):
    # g.engagement_role is set by the decorator
    pass
```

Role hierarchy: `owner` (3) > `editor` (2) > `viewer` (1). Admins automatically get `owner` access to all engagements.

## Anti-Patterns

### WARNING: Storing Secrets in JWT Payload

**The Problem:**
```python
# BAD — payload is base64-encoded, NOT encrypted
payload = {'user_id': 1, 'password': password, 'api_key': key}
```

**Why This Breaks:** Anyone can decode a JWT without the secret key. `base64.b64decode(token.split('.')[1])` reveals the full payload. Sensitive data becomes readable to any network observer or log system.

**The Fix:** Only store non-sensitive identifiers: `user_id`, `role`, `username`, `exp`.

### WARNING: Accepting Algorithm from Token Header

**The Problem:**
```python
# BAD — algorithm confusion attack
alg = jwt.get_unverified_header(token)['alg']
jwt.decode(token, secret, algorithms=[alg])
```

**Why This Breaks:** Attacker sets `alg: "none"` and removes the signature, or sets `alg: "HS256"` with a known RS256 public key as the HMAC secret.

**The Fix:**
```python
# GOOD — explicit algorithm list
jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
```

### WARNING: Exposing JWT Errors to Clients

**The Problem:**
```python
# BAD — leaks internal state
except JWTError as e:
    return jsonify({"error": str(e)}), 401  # "Signature has expired" reveals timing
```

**Why This Breaks:** Error messages reveal whether the token was expired vs. malformed vs. wrong signature, helping attackers refine forgery attempts.

**The Fix:**
```python
# GOOD — generic response for all JWT failures
except JWTError:
    return jsonify({"error": "unauthorized"}), 401
```

### WARNING: Storing JWT in localStorage

**The Problem:**
```javascript
// BAD — accessible to any XSS payload
localStorage.setItem('token', jwt);
fetch('/api/data', { headers: { Authorization: `Bearer ${jwt}` } });
```

**Why This Breaks:** Any XSS vulnerability (even in a third-party script) can read `localStorage` and exfiltrate the token. httpOnly cookies are invisible to JavaScript.

**The Fix:** PTVault uses httpOnly cookies. The browser sends them automatically — no JS token management needed.

## Configuration Reference

```python
# config.py:17-19
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or \
    base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
JWT_EXPIRY_HOURS = int(os.environ.get('JWT_EXPIRY_HOURS', 24))
```

**Production requirements:**
- Set `JWT_SECRET_KEY` via environment variable — auto-generated keys change on restart, invalidating all sessions
- Use at least 256 bits of randomness (32 bytes)
- Never commit secrets to version control

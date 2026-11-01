# Argon2 Patterns Reference

## Contents
- Singleton PasswordHasher
- Hashing Patterns
- Verification Pattern
- Rehashing on Parameter Upgrade
- WARNING: Never Roll Your Own Comparison
- WARNING: Never Store Parameters Separately
- WARNING: Never Log or Return Hash Details
- Integration with Flask Routes

## Singleton PasswordHasher

PTVault uses a module-level `PasswordHasher` instance to guarantee consistent parameters.

```python
# models/auth.py - module-level singleton
from argon2 import PasswordHasher
from argon2.low_level import Type

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    type=Type.ID
)
```

**Why singleton:** Creating new instances risks parameter drift. If one route uses `time_cost=2` and another uses `time_cost=3`, hashes become inconsistent and verification fails silently.

## Hashing Patterns

PTVault exposes two pairs of functions. `hash_password`/`verify_password` are the canonical multi-user versions. `hash_master_password`/`verify_master_password` are legacy aliases for backward compatibility.

```python
# models/auth.py - both use the same singleton
def hash_master_password(password: str) -> str:
    return ph.hash(password)

def hash_password(password: str) -> str:
    return ph.hash(password)
```

Always validate password strength before hashing:

```python
# routes/auth.py:42-43 and routes/users.py:87-88
if len(master_password) < 8:
    raise ValidationError("Password must be at least 8 characters", field='master_password')
```

## Verification Pattern

```python
# models/auth.py:69-85
def verify_password(password: str, hash: str) -> bool:
    try:
        ph.verify(hash, password)
        return True
    except Exception:
        return False
```

**Note the argument order:** `ph.verify(hash, password)` -- hash first, password second. This is the `argon2-cffi` convention and the opposite of what you might expect.

Catches all exceptions to return a simple boolean. This prevents timing analysis from different exception code paths.

## Rehashing on Parameter Upgrade

When you change Argon2 parameters (e.g., increasing `time_cost`), existing hashes still verify but use old settings. Use `check_needs_rehash()` to transparently upgrade:

```python
# Not currently used in PTVault, but implement when upgrading parameters
def verify_and_rehash(password: str, stored_hash: str, cursor, user_id: int) -> bool:
    if not verify_password(password, stored_hash):
        return False
    if ph.check_needs_rehash(stored_hash):
        new_hash = ph.hash(password)
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
    return True
```

---

## WARNING: Never Roll Your Own Comparison

**The Problem:**

```python
# BAD - Timing attack vulnerability AND fundamentally broken
def verify_password(password: str, hash: str) -> bool:
    new_hash = ph.hash(password)
    return new_hash == hash  # Each hash() generates a new random salt
```

**Why This Breaks:**
1. `ph.hash()` generates a new random salt each time, so two hashes of the same password will NEVER be equal -- this approach simply does not work
2. Even if you somehow used the same salt, string `==` exits early on first differing character, leaking timing information
3. Attackers measure response time to deduce hash contents character by character

**The Fix:**

```python
# GOOD - Use ph.verify() which extracts salt from stored hash
def verify_password(password: str, hash: str) -> bool:
    try:
        ph.verify(hash, password)
        return True
    except Exception:
        return False
```

---

## WARNING: Never Store Parameters Separately

**The Problem:**

```python
# BAD - Parameters stored separately from hash
CREATE TABLE users (
    password_hash TEXT,
    argon2_time_cost INTEGER,
    argon2_memory_cost INTEGER
)
```

**Why This Breaks:**
1. Parameters can get out of sync with the actual hash
2. Migration nightmares when upgrading Argon2 settings
3. Argon2 hash format already embeds all parameters -- storing separately is redundant

**The Fix:**

```python
# GOOD - Store the full hash string (PTVault approach)
CREATE TABLE users (
    password_hash TEXT NOT NULL  -- $argon2id$v=19$m=65536,t=3,p=4$salt$hash
)
```

---

## WARNING: Never Log or Return Hash Details

**The Problem:**

```python
# BAD - Leaking hash info in error responses or logs
logger.info(f"Login failed for hash: {stored_hash}")
return jsonify({"error": "invalid password", "hash": stored_hash}), 401
```

**Why This Breaks:**
1. Hash strings contain the salt -- exposing it removes half the protection
2. Log files are often less protected than the database
3. Error responses could be captured by attackers

**The Fix:**

```python
# GOOD - Generic error, no hash details (PTVault pattern)
logger.warning(f"Failed login attempt for user_id={user_id}")
raise AuthenticationError("Invalid credentials")
```

---

## Integration with Flask Routes

### Setup Endpoint (First-Time Admin Creation)

```python
# routes/auth.py:59-64
password_hash = hash_master_password(master_password)
cursor.execute('''
    INSERT INTO users (username, email, full_name, password_hash, role, is_active)
    VALUES (?, ?, ?, ?, 'admin', 1)
''', (username, email, full_name, password_hash))
```

### Login Endpoint (Multi-User)

```python
# routes/auth.py:149-151
if not verify_password(password, password_hash):
    raise AuthenticationError("Invalid credentials")
# On success, create JWT session -- see the **jwt** skill
token = create_session_token(user_id, role=role, username=db_username)
```

### Password Change (User Update)

```python
# routes/users.py:170-174
if 'password' in data:
    if len(data['password']) < 8:
        raise ValidationError("Password must be at least 8 characters")
    update_data['password_hash'] = hash_password(data['password'])
```

## Password Validation Checklist

Copy this checklist when adding new password endpoints:

- [ ] Validate minimum length (8 characters)
- [ ] Hash with `hash_password()` from `models/auth.py`
- [ ] Store in `password_hash` column (full Argon2 string)
- [ ] Verify with `verify_password()`, never manual comparison
- [ ] Return generic "Invalid credentials" on failure
- [ ] Never log or return hash values

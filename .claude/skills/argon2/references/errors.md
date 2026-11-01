# Argon2 Errors Reference

## Contents
- Exception Hierarchy
- VerifyMismatchError
- InvalidHashError
- HashingError
- PTVault Error Handling Strategy
- WARNING: Never Catch Specific Exceptions in Verify
- Debugging Invalid Hashes
- Error Recovery Checklist

## Exception Hierarchy

```
argon2.exceptions
├── VerifyMismatchError  # Password doesn't match hash
├── VerificationError    # General verification failure (base class)
├── InvalidHashError     # Malformed hash string
└── HashingError         # Hashing operation failed (OOM, bad params)
```

## VerifyMismatchError

Most common exception -- raised when the password is simply wrong.

```python
from argon2.exceptions import VerifyMismatchError

try:
    ph.verify(stored_hash, user_password)
except VerifyMismatchError:
    # Password incorrect -- normal "wrong password" case
    pass
```

## InvalidHashError

Raised when the hash string is malformed or from an incompatible implementation.

```python
# These all raise InvalidHashError:
ph.verify("not_a_valid_hash", "password")
ph.verify("$argon2id$truncated", "password")
ph.verify("", "password")
```

Common causes:
- Hash truncated during database storage (column too narrow)
- Hash from a different algorithm (bcrypt `$2b$`, scrypt) passed to Argon2
- Corrupted data in database
- Empty string stored instead of hash

## HashingError

Raised when the hashing operation itself fails (rare).

```python
# May raise HashingError if system can't allocate memory
ph = PasswordHasher(memory_cost=999999999)
ph.hash("password")  # Memory allocation failure
```

Common causes:
- `memory_cost` exceeds available system memory
- Docker container memory limits too restrictive (`--memory` flag)
- System under extreme resource pressure

---

## PTVault Error Handling Strategy

PTVault deliberately catches all exceptions in verify functions:

```python
# models/auth.py:69-85
def verify_password(password: str, hash: str) -> bool:
    try:
        ph.verify(hash, password)
        return True
    except Exception:  # Intentionally broad
        return False
```

**Why catch `Exception` instead of specific types:**
1. **Timing consistency** -- Different exception types take different code paths. Catching everything makes the response time uniform
2. **Simplicity** -- Route handlers get a clean boolean without importing argon2 exceptions
3. **Security** -- No exception details leak to callers or logs

Route handlers use the boolean with PTVault's error handler:

```python
# routes/auth.py:149-151
if not verify_password(password, password_hash):
    raise AuthenticationError("Invalid credentials")
```

See the **flask** skill for the `AuthenticationError` and `@handle_errors` patterns.

---

## WARNING: Never Catch Specific Exceptions in Verify

**The Problem:**

```python
# BAD - Different code paths leak timing information
def verify_password(password: str, hash: str) -> bool:
    try:
        ph.verify(hash, password)
        return True
    except VerifyMismatchError:
        return False  # Fast path
    except InvalidHashError:
        logger.error("Corrupt hash detected")  # Slow path (logging I/O)
        return False
    except Exception:
        logger.error("Unknown error")  # Different slow path
        return False
```

**Why This Breaks:**
1. Each except branch has different execution time due to logging I/O
2. Attackers can distinguish "wrong password" from "corrupt hash" by measuring response latency
3. Information about hash validity leaks through timing

**The Fix:**

```python
# GOOD - Single code path, uniform timing
def verify_password(password: str, hash: str) -> bool:
    try:
        ph.verify(hash, password)
        return True
    except Exception:
        return False
```

If you need to detect corrupt hashes, do it in a separate admin/maintenance function, never in the login path.

---

## Debugging Invalid Hashes

Parse hash components to diagnose issues:

```python
def parse_argon2_hash(hash_str: str) -> dict:
    """Debug helper -- NOT for production use."""
    if not hash_str or not hash_str.startswith('$argon2'):
        return {"error": "Not an Argon2 hash"}

    parts = hash_str.split('$')
    # ['', 'argon2id', 'v=19', 'm=65536,t=3,p=4', 'salt_b64', 'hash_b64']
    if len(parts) < 6:
        return {"error": f"Truncated hash, only {len(parts)} parts (need 6)"}

    params = dict(p.split('=') for p in parts[3].split(','))
    return {
        "variant": parts[1],
        "version": parts[2],
        "memory_kib": int(params.get('m', 0)),
        "time_cost": int(params.get('t', 0)),
        "parallelism": int(params.get('p', 0)),
        "salt_b64": parts[4],
        "hash_b64": parts[5]
    }
```

### Quick Hash Validation

```python
def is_valid_argon2_hash(hash_str: str) -> bool:
    """Sanity check before attempting verification."""
    if not hash_str or not isinstance(hash_str, str):
        return False
    if not hash_str.startswith('$argon2'):
        return False
    return len(hash_str.split('$')) >= 6
```

## Rehash Detection

When upgrading Argon2 parameters, detect hashes that need updating:

```python
# argon2-cffi built-in
if ph.check_needs_rehash(stored_hash):
    # Stored hash uses old parameters (e.g., time_cost=2)
    # Current PasswordHasher uses time_cost=3
    new_hash = ph.hash(password)
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
```

`check_needs_rehash()` returns `True` when embedded parameters differ from `PasswordHasher` config.

## Error Recovery Checklist

Copy this checklist when debugging Argon2 issues:

- [ ] Verify `argon2-cffi` installed: `pip show argon2-cffi`
- [ ] Check hash format starts with `$argon2`: `SELECT password_hash FROM users LIMIT 1`
- [ ] Confirm hash not truncated (should be ~97 chars)
- [ ] Test with known password: `ph.verify(stored_hash, "known_password")`
- [ ] Check available memory vs `memory_cost` setting (64MB per hash)
- [ ] Verify PasswordHasher parameters in `models/auth.py:14-20`
- [ ] Check `ph.verify()` argument order: `(hash, password)` not `(password, hash)`

### Debugging Workflow

1. Check if hashing works: `python3 -c "from models.auth import ph; print(ph.hash('test'))"`
2. If hashing works but verification fails, check argument order in `ph.verify()`
3. If `InvalidHashError`, inspect stored hash in database for truncation
4. If `HashingError`, check system memory and container limits
5. Only proceed to code changes when root cause is identified

# PyNaCl Patterns Reference

## Contents
- SecretBox Encryption
- Key Management
- Base64 Storage Pattern
- Anti-Patterns

## SecretBox Encryption

SecretBox is the only PyNaCl primitive PTVault uses. It provides authenticated symmetric encryption (XSalsa20-Poly1305).

### Encrypt with Auto-Nonce (Preferred)

```python
import nacl.secret
import nacl.utils

key = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
box = nacl.secret.SecretBox(key)

# Nonce is auto-generated and prepended to ciphertext
encrypted = box.encrypt(b"credential: admin:P@ssw0rd")
# encrypted = nonce (24 bytes) + ciphertext + MAC (16 bytes)

decrypted = box.decrypt(encrypted)
```

### Encrypt with Explicit Nonce (Rare)

Only use when you need nonce tracking for deduplication or ordering.

```python
nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)  # 24 bytes
encrypted = box.encrypt(b"data", nonce=nonce)
```

## Key Management

### Deriving Encryption Key from User Password

Use Argon2id low-level API to derive a 32-byte key. See the **argon2** skill for parameter details.

```python
from argon2.low_level import hash_secret_raw, Type
import nacl.utils

def derive_encryption_key(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """Derive a SecretBox key from password. Returns (key, salt)."""
    if salt is None:
        salt = nacl.utils.random(16)
    key = hash_secret_raw(
        secret=password.encode('utf-8'),
        salt=salt,
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        type=Type.ID
    )
    return key, salt
```

### Storing Keys in Memory

```python
# GOOD - Key lives only during request lifecycle
@require_auth
def get_sensitive_data():
    key = derive_key_from_session(g.current_user)
    box = nacl.secret.SecretBox(key)
    # decrypt, use, let key go out of scope

# BAD - Key persisted as module-level global
ENCRYPTION_KEY = derive_key(...)  # Lives forever in memory
```

## Base64 Storage Pattern

SQLite TEXT columns store base64-encoded ciphertext. This avoids binary encoding issues.

```python
import base64
import nacl.secret

def encrypt_for_storage(plaintext: str, key: bytes) -> str:
    """Encrypt and encode for SQLite TEXT storage."""
    box = nacl.secret.SecretBox(key)
    ct = box.encrypt(plaintext.encode('utf-8'))
    return base64.b64encode(ct).decode('ascii')

def decrypt_from_storage(stored: str, key: bytes) -> str:
    """Decode and decrypt from SQLite TEXT storage."""
    box = nacl.secret.SecretBox(key)
    ct = base64.b64decode(stored)
    return box.decrypt(ct).decode('utf-8')
```

Store the salt alongside the ciphertext in the database:

```sql
-- Example: adding encrypted fields to host_credentials
ALTER TABLE host_credentials ADD COLUMN encrypted_password TEXT;
ALTER TABLE host_credentials ADD COLUMN encryption_salt BLOB;
```

## Anti-Patterns

### WARNING: Reusing Keys Across Engagements

**The Problem:**

```python
# BAD - Same key for all engagements
GLOBAL_KEY = nacl.utils.random(32)

def encrypt_evidence(data, engagement_id):
    box = nacl.secret.SecretBox(GLOBAL_KEY)
    return box.encrypt(data)
```

**Why This Breaks:**
1. Compromising one key exposes ALL engagement data across ALL clients
2. Violates PTVault's per-engagement data isolation principle
3. No way to rotate keys per-engagement or revoke access

**The Fix:**

```python
# GOOD - Per-engagement key derived from master password + engagement salt
def get_engagement_key(password: str, engagement_salt: bytes) -> bytes:
    key, _ = derive_encryption_key(password, salt=engagement_salt)
    return key
```

### WARNING: Storing Raw Key Material in Database

**The Problem:**

```python
# BAD - Key stored in plaintext
cursor.execute('INSERT INTO keys (engagement_id, key) VALUES (?, ?)',
               (eid, base64.b64encode(key)))
```

**Why This Breaks:**
1. Database compromise = all keys compromised = all data compromised
2. Encryption becomes security theater

**The Fix:**

Derive keys from the user's password at runtime. Never persist raw key material. The key exists only in memory during the authenticated session.

### WARNING: Catching nacl.exceptions.CryptoError Silently

**The Problem:**

```python
# BAD - Silent decryption failure hides tampering
try:
    plaintext = box.decrypt(ciphertext)
except Exception:
    plaintext = ""  # Returns empty string, hides corruption
```

**Why This Breaks:**
1. `CryptoError` means the data was tampered with or the wrong key was used
2. Silent failure masks security incidents
3. Returning empty string may propagate bad data downstream

**The Fix:**

```python
import nacl.exceptions

try:
    plaintext = box.decrypt(ciphertext)
except nacl.exceptions.CryptoError:
    # Log the event, alert the user, do NOT return fake data
    raise DecryptionError(f"Decryption failed for record {record_id} - possible tampering")
```

### WARNING: Using nacl.secret for Password Hashing

**The Problem:**

```python
# BAD - SecretBox is encryption, not hashing
key = nacl.utils.random(32)
box = nacl.secret.SecretBox(key)
"hash" = box.encrypt(password.encode())
```

**Why This Breaks:**
1. Encryption is reversible; password hashing must be one-way
2. Anyone with the key can recover all passwords
3. No memory-hardness against brute force

**The Fix:**

Use Argon2id for password hashing. See the **argon2** skill.

```python
from models.auth import hash_password, verify_password

stored_hash = hash_password(password)
is_valid = verify_password(submitted, stored_hash)
```

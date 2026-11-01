# PyNaCl Workflows Reference

## Contents
- Adding Field-Level Encryption
- Key Derivation Flow
- Encrypting Evidence Attachments
- Testing Encryption

## Adding Field-Level Encryption

When adding encryption to a database field (e.g., `host_credentials.password`), follow this workflow.

Copy this checklist and track progress:
- [ ] Step 1: Add migration for encrypted column + salt column
- [ ] Step 2: Create encrypt/decrypt helper functions
- [ ] Step 3: Update DAO to encrypt on write, decrypt on read
- [ ] Step 4: Update route to pass key from session context
- [ ] Step 5: Write tests with known key/plaintext pairs
- [ ] Step 6: Verify decryption failure raises explicit error

### Step 1: Migration

See the **sqlite** skill for migration conventions.

```python
# models/migrations/versions/016_encrypt_credentials.py
def upgrade(cursor):
    cursor.execute('''
        ALTER TABLE host_credentials
        ADD COLUMN encrypted_password TEXT
    ''')
    cursor.execute('''
        ALTER TABLE host_credentials
        ADD COLUMN password_salt BLOB
    ''')

def downgrade(cursor):
    pass  # SQLite cannot DROP COLUMN before 3.35
```

### Step 2: Encryption Helpers

Place in `models/auth.py` alongside existing crypto imports.

```python
# models/auth.py - add to existing file
import nacl.secret
import nacl.utils
import nacl.exceptions
import base64
from argon2.low_level import hash_secret_raw, Type

def derive_encryption_key(password: str, salt: bytes) -> bytes:
    """Derive 32-byte SecretBox key from password + salt."""
    return hash_secret_raw(
        secret=password.encode('utf-8'),
        salt=salt,
        time_cost=3, memory_cost=65536,
        parallelism=4, hash_len=32, type=Type.ID
    )

def encrypt_field(plaintext: str, key: bytes) -> str:
    """Encrypt string to base64 for SQLite TEXT storage."""
    box = nacl.secret.SecretBox(key)
    return base64.b64encode(box.encrypt(plaintext.encode('utf-8'))).decode('ascii')

def decrypt_field(ciphertext_b64: str, key: bytes) -> str:
    """Decrypt base64 ciphertext back to string."""
    box = nacl.secret.SecretBox(key)
    return box.decrypt(base64.b64decode(ciphertext_b64)).decode('utf-8')
```

### Step 3: DAO Integration

```python
# models/dao/host_dao.py - credential storage
def save_credential(self, host_id, username, password, key):
    salt = nacl.utils.random(16)
    enc_key = derive_encryption_key_from_master(key, salt)
    encrypted_pw = encrypt_field(password, enc_key)

    self.cursor.execute('''
        INSERT INTO host_credentials (host_id, username, encrypted_password, password_salt)
        VALUES (?, ?, ?, ?)
    ''', (host_id, username, encrypted_pw, salt))
```

### Step 4: Route Integration

See the **flask** skill for route patterns.

```python
# routes/hosts.py
@hosts_bp.route('/api/hosts/<int:host_id>/credentials', methods=['POST'])
@require_auth
def add_credential(host_id):
    data = request.get_json()
    # Key derived from session - never stored
    encryption_key = get_session_encryption_key(g.current_user)
    host_dao.save_credential(
        host_id, data['username'], data['password'], encryption_key
    )
    return jsonify({"status": "saved"}), 201
```

## Key Derivation Flow

```
User Password
     |
     v
Argon2id(password, salt, t=3, m=64MB, p=4)
     |
     v
32-byte Key ──> nacl.secret.SecretBox(key)
     |                    |
     v                    v
  (memory only)    encrypt() / decrypt()
     |
     v
  Discarded on logout
```

The salt must be stored per-encrypted-field (or per-engagement). The derived key lives only in memory during the authenticated session.

### Validation Loop

1. Encrypt test data with derived key
2. Decrypt and verify: `assert decrypt_field(encrypted, key) == original`
3. If assertion fails, check salt storage and key derivation parameters
4. Only proceed to production use when round-trip passes

## Encrypting Evidence Attachments

For file-based evidence (screenshots, tool output), encrypt the file content before writing to disk.

```python
import nacl.secret
import nacl.utils

def encrypt_file(input_path: str, output_path: str, key: bytes):
    """Encrypt a file using SecretBox. Adds 40 bytes overhead."""
    box = nacl.secret.SecretBox(key)
    with open(input_path, 'rb') as f:
        plaintext = f.read()
    encrypted = box.encrypt(plaintext)
    with open(output_path, 'wb') as f:
        f.write(encrypted)

def decrypt_file(encrypted_path: str, key: bytes) -> bytes:
    """Decrypt a file, returns raw bytes."""
    box = nacl.secret.SecretBox(key)
    with open(encrypted_path, 'rb') as f:
        ciphertext = f.read()
    return box.decrypt(ciphertext)
```

WARNING: For files larger than ~100MB (PTVault's max upload is 250MB), read and encrypt in chunks. SecretBox operates on the full message, so chunked encryption requires encrypting each chunk separately with unique nonces and reassembling on decryption.

## Testing Encryption

See the **pytest** skill for test conventions.

### Unit Test Pattern

```python
# tests/test_encryption.py
import nacl.secret
import nacl.utils
import pytest

def test_encrypt_decrypt_roundtrip():
    key = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
    box = nacl.secret.SecretBox(key)
    plaintext = b"SQL injection in /admin/login"
    encrypted = box.encrypt(plaintext)
    assert box.decrypt(encrypted) == plaintext

def test_wrong_key_raises_crypto_error():
    key1 = nacl.utils.random(32)
    key2 = nacl.utils.random(32)
    box1 = nacl.secret.SecretBox(key1)
    box2 = nacl.secret.SecretBox(key2)
    encrypted = box1.encrypt(b"secret")
    with pytest.raises(nacl.exceptions.CryptoError):
        box2.decrypt(encrypted)

def test_tampered_ciphertext_raises_error():
    key = nacl.utils.random(32)
    box = nacl.secret.SecretBox(key)
    encrypted = bytearray(box.encrypt(b"data"))
    encrypted[-1] ^= 0xFF  # Flip last byte
    with pytest.raises(nacl.exceptions.CryptoError):
        box.decrypt(bytes(encrypted))
```

### Integration Test with Key Derivation

```python
def test_password_derived_key_roundtrip():
    from models.auth import derive_encryption_key, encrypt_field, decrypt_field
    password = "TestP@ssw0rd!"
    salt = nacl.utils.random(16)
    key = derive_encryption_key(password, salt)
    original = "admin:hunter2"
    encrypted = encrypt_field(original, key)
    assert decrypt_field(encrypted, key) == original

    # Same password + same salt = same key
    key2 = derive_encryption_key(password, salt)
    assert decrypt_field(encrypted, key2) == original
```

## Error Handling

Always handle `nacl.exceptions.CryptoError` explicitly. This exception means one of:
- Wrong decryption key (user changed password, wrong engagement key)
- Ciphertext was tampered with (data integrity violation)
- Ciphertext is corrupted (storage error)

```python
import nacl.exceptions

try:
    plaintext = decrypt_field(stored_value, key)
except nacl.exceptions.CryptoError:
    # Log for audit trail - see audit_logger.py
    audit_log("decryption_failure", user_id=g.current_user['id'],
              detail="Failed to decrypt credential")
    return jsonify({"error": "Unable to decrypt data. Verify your credentials."}), 403
```

NEVER return raw `CryptoError` messages to the client. They leak implementation details.

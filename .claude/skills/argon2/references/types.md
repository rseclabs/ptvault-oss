# Argon2 Types Reference

## Contents
- Hash String Format
- PasswordHasher Parameters
- Argon2 Variant Types
- PTVault Function Signatures
- Database Column Type
- Parameter Tuning Guide

## Hash String Format

Argon2 produces self-describing hash strings. All parameters needed for verification are embedded:

```
$argon2id$v=19$m=65536,t=3,p=4$<base64-salt>$<base64-hash>
```

| Component | Value | Meaning |
|-----------|-------|---------|
| `argon2id` | Variant | Hybrid Argon2 (PTVault default) |
| `v=19` | Version | Argon2 version 1.3 |
| `m=65536` | Memory | 64MB (65536 KiB) |
| `t=3` | Time | 3 iterations |
| `p=4` | Parallelism | 4 threads |
| `<salt>` | Base64 | Random 16-byte salt (auto-generated) |
| `<hash>` | Base64 | 32-byte derived key |

## PasswordHasher Parameters

```python
from argon2 import PasswordHasher
from argon2.low_level import Type

PasswordHasher(
    time_cost: int = 3,        # Iterations (minimum 1)
    memory_cost: int = 65536,  # KiB of memory (minimum 8)
    parallelism: int = 4,      # Threads (minimum 1)
    hash_len: int = 32,        # Output bytes
    salt_len: int = 16,        # Salt bytes (auto-generated)
    encoding: str = 'utf-8',   # Password string encoding
    type: Type = Type.ID       # Argon2 variant
)
```

All parameters except `encoding` affect the hash output. Changing any parameter means old hashes won't match a naive comparison -- but `ph.verify()` reads parameters from the hash string itself, so verification always works regardless of current `PasswordHasher` settings.

## Argon2 Variant Types

```python
from argon2.low_level import Type

Type.D   # Argon2d  - GPU-resistant, vulnerable to side-channel attacks
Type.I   # Argon2i  - Side-channel resistant, less GPU-resistant
Type.ID  # Argon2id - Hybrid (RECOMMENDED by RFC 9106)
```

**PTVault uses `Type.ID`:**
- First pass: Argon2i mode (side-channel resistance)
- Subsequent passes: Argon2d mode (GPU/ASIC resistance)

NEVER use `Type.D` for password hashing in server applications. It's only appropriate when side-channel attacks are impossible (e.g., cryptocurrency proof-of-work).

## PTVault Function Signatures

```python
# models/auth.py

def hash_master_password(password: str) -> str:
    """Returns full Argon2id hash string. Legacy single-user."""

def hash_password(password: str) -> str:
    """Returns full Argon2id hash string. Multi-user."""

def verify_master_password(password: str, hash: str) -> bool:
    """Constant-time verification. Legacy single-user."""

def verify_password(password: str, hash: str) -> bool:
    """Constant-time verification. Multi-user."""
```

Input type: always `str`. The `argon2-cffi` library handles UTF-8 encoding internally.

Return types:
- Hash functions return `str` -- the full `$argon2id$...` string
- Verify functions return `bool` -- `True` on match, `False` on any failure

## Database Column Type

```sql
-- models/schema.sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    password_hash TEXT NOT NULL,  -- Full Argon2 hash string (~97 chars)
    role TEXT NOT NULL DEFAULT 'tester',
    is_active INTEGER DEFAULT 1,
    ...
);
```

The `password_hash` column is `TEXT` because the Argon2 encoded string is variable-length (typically ~97 characters). NEVER use a fixed-width column like `CHAR(60)` -- that's for bcrypt, not Argon2.

See the **sqlite** skill for schema conventions.

## Parameter Tuning Guide

| Environment | time_cost | memory_cost | parallelism | Notes |
|-------------|-----------|-------------|-------------|-------|
| Tests | 1 | 16384 | 1 | Fast tests, not for production |
| Development | 2 | 32768 | 2 | Faster iteration |
| **Production (PTVault)** | **3** | **65536** | **4** | **Current settings** |
| High Security | 4-6 | 131072+ | 4-8 | For high-value targets |

**PTVault rationale:**
- `time_cost=3`: ~300ms per hash on modern hardware. Users tolerate up to ~1s for login
- `memory_cost=65536`: 64MB per hash. Makes parallel GPU attacks require massive VRAM
- `parallelism=4`: Utilizes multi-core CPUs. Setting higher than available cores wastes resources

**Tuning process:**
1. Set `memory_cost` as high as your server can sustain under peak load
2. Increase `time_cost` until hashing takes ~300-500ms
3. Set `parallelism` to half available CPU cores
4. Validate: `python3 -c "from models.auth import ph; import time; t=time.time(); ph.hash('test'); print(f'{(time.time()-t)*1000:.0f}ms')"`

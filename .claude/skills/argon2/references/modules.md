# Argon2 Modules Reference

## Contents
- Core Imports
- Package Architecture
- PTVault Module Organization
- Low-Level API
- Testing and Verification
- Dependency Chain

## Core Imports

```python
# Standard usage in PTVault (models/auth.py)
from argon2 import PasswordHasher
from argon2.low_level import Type
```

Only these two imports are needed. AVOID importing exceptions directly in route handlers -- use the wrapper functions in `models/auth.py` instead, which handle exceptions internally.

## Package Architecture

```
argon2-cffi (pip install argon2-cffi>=23.1.0)
    argon2/
    ├── __init__.py          # PasswordHasher class
    ├── exceptions.py        # VerifyMismatchError, InvalidHash, etc.
    ├── low_level.py         # Type enum, hash_secret_raw()
    └── _password_hasher.py  # Implementation details

argon2-cffi-bindings (auto-installed dependency)
    └── libargon2 (C reference implementation)
```

The `argon2-cffi` package wraps the reference C implementation via CFFI bindings. No pure-Python fallback exists -- the C library must compile during installation.

## PTVault Module Organization

```
models/
├── auth.py              # Argon2 hashing + JWT token functions
│   ├── ph               # PasswordHasher singleton (line 14-20)
│   ├── hash_master_password()    # Legacy hash (line 23)
│   ├── hash_password()           # Multi-user hash (line 36)
│   ├── verify_master_password()  # Legacy verify (line 50)
│   ├── verify_password()         # Multi-user verify (line 69)
│   ├── create_session_token()    # JWT creation (line 88)
│   └── verify_session_token()    # JWT verification (line 111)

routes/
├── auth.py              # /api/auth/* endpoints
│   ├── setup()          # First-time admin + hash_master_password
│   ├── login()          # Verify + create session token
│   └── logout()         # Clear cookie
│
└── users.py             # /api/users/* endpoints
    ├── create_user()    # hash_password for new users
    └── update_user()    # hash_password for password changes

middleware/
└── auth.py              # @require_auth uses verify_session_token
```

### Import Pattern for Route Handlers

```python
# routes/auth.py - import only the functions you need
from models.auth import (
    hash_master_password,
    verify_master_password,
    create_session_token,
    hash_password,
    verify_password
)
```

```python
# routes/users.py - only needs hash_password for user management
from models.auth import hash_password
```

See the **flask** skill for Blueprint registration patterns.

## Low-Level API

For key derivation (not password storage), use the low-level API:

```python
from argon2.low_level import hash_secret_raw, Type

# Derive an encryption key from a password
raw_key = hash_secret_raw(
    secret=b"user_password",
    salt=b"sixteen_byte_sal",  # Must provide your own salt
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    type=Type.ID
)
# Returns: bytes (raw 32-byte key, no encoding)
```

**When to use low-level vs PasswordHasher:**

| Scenario | Use |
|----------|-----|
| Password storage/verification | `PasswordHasher` (high-level) |
| Deriving encryption keys | `hash_secret_raw` (low-level) |
| Custom salt management | `hash_secret_raw` (low-level) |
| Interop with non-Python Argon2 | `hash_secret_raw` (low-level) |

PTVault uses PyNaCl for encryption, not Argon2 key derivation. See the **pynacl** skill.

## Testing and Verification

### Quick Installation Check

```bash
pip show argon2-cffi
python3 -c "from argon2 import PasswordHasher; print('OK')"
```

### Verify PTVault Parameters

```bash
python3 -c "
from models.auth import ph
h = ph.hash('test')
print('Hash:', h[:60] + '...')
print('Needs rehash:', ph.check_needs_rehash(h))
ph.verify(h, 'test')
print('Verify: OK')
"
```

### Benchmark Hash Time

```bash
python3 -c "
import time
from models.auth import ph
start = time.time()
ph.hash('benchmark_password')
elapsed = (time.time() - start) * 1000
print(f'Hash time: {elapsed:.0f}ms')
# Should be 200-500ms for production settings
"
```

## Dependency Chain

```
# requirements.txt
argon2-cffi>=23.1.0

# Auto-installed by argon2-cffi:
argon2-cffi-bindings  # C library bindings via CFFI

# Other models/auth.py dependencies:
python-jose[cryptography]>=3.3.0  # JWT tokens (see **jwt** skill)
PyNaCl>=1.5.0                     # Encryption (see **pynacl** skill)
```

### Installation Troubleshooting

If `argon2-cffi` fails to install, the C bindings need a compiler:

```bash
# Debian/Ubuntu/Kali
sudo apt-get install -y build-essential python3-dev libffi-dev

# Then retry
pip install argon2-cffi>=23.1.0
```

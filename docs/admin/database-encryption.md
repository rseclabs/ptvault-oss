# Database Encryption

PTVault optionally encrypts the SQLite database using **SQLCipher**, providing AES-256 encryption at rest. This protects all engagement data, credentials, and evidence if the database file is accessed outside of PTVault.

## Requirements

Database encryption uses the `sqlcipher3` Python package, which `pip install -r requirements.txt` installs automatically. Its prebuilt wheels include SQLCipher for Linux, macOS and Windows, so no system libraries are needed. The Docker image includes it too.

If `sqlcipher3` is not installed, the encryption option in Admin Settings shows as **Unavailable**, and `pip install sqlcipher3` fixes it.

## Checking Encryption Status

1. Go to **Admin > Settings**
2. Find the **Database Encryption** section

The status panel shows:

| Field | Description |
|-------|-------------|
| **Available** | Whether SQLCipher is installed |
| **Enabled** | Whether the current database is encrypted |
| **Key** | Where the key is kept: in memory (the default), or also in a key file with the `PTVAULT_STORE_KEY_FILE` opt-in |
| **Salt File Exists** | Whether the salt file (for key derivation) is present |
| **Required by Policy** | Whether the `PTVAULT_ENCRYPTION_REQUIRED` env var prevents disabling |

## Enabling Encryption

1. Go to **Admin > Settings** → Database Encryption
2. Click **Enable Encryption**
3. Choose the **database passphrase** (used to derive the encryption key)
4. Click **Confirm**

PTVault will:
1. Derive an AES-256 key from your password using Argon2id + a random salt
2. Save the salt to `encryption.salt` beside the database
3. Encrypt the database file in place using SQLCipher
4. Keep the key in memory only; it is never written to disk

The process takes a few seconds for typical database sizes. PTVault remains available throughout.

> **Important:** After every restart PTVault is locked: every page shows an unlock form until the database passphrase is entered (`POST /api/unlock`, limited to 5 attempts a minute). Back up `encryption.salt` with the database and keep the passphrase safe; without both the database cannot be decrypted.

### Unattended restarts

For a server that must come up without someone typing the passphrase:

- `PTVAULT_DB_PASSPHRASE` unlocks at startup. The passphrase is then in the process environment, readable by anyone who can inspect the process or its configuration.
- `PTVAULT_STORE_KEY_FILE=1` writes the derived key to `PTVAULT_ENCRYPTION_KEY_FILE` as older versions did. Anyone who can read that file can open the database, so the encryption then protects only a copy of the database taken without the key file.

Upgrading: a key file written by an older version is deleted the first time the database is unlocked with the passphrase (unless `PTVAULT_STORE_KEY_FILE=1`).

## Disabling Encryption

1. Go to **Admin > Settings** → Database Encryption
2. Click **Disable Encryption**
3. Enter your admin password
4. Click **Confirm**

PTVault decrypts the database and forgets the key (the salt file is kept).

> **Note:** Disabling encryption is blocked while encryption is required, which is the default. Set `PTVAULT_ENCRYPTION_REQUIRED=0` to allow it.

## Key Recovery

The key is re-derived from the database passphrase and the salt file whenever the database is unlocked, so there is no key file to lose. After a restart every page redirects to the **unlock page** (`/unlock`); enter the database passphrase there. There is no separate recovery step.

If the salt file is lost, or the passphrase is forgotten, the database **cannot be recovered** without brute-forcing the key. This is by design.

## Security Architecture

| Component | Details |
|-----------|---------|
| Encryption algorithm | AES-256 (via SQLCipher) |
| Key derivation | Argon2id (time_cost=3, memory=64MiB) + random 32-byte salt |
| Key storage | Memory only (the `PTVAULT_STORE_KEY_FILE=1` opt-in writes `encryption.key`) |
| Salt storage | `encryption.salt` beside the database |
| Database format | SQLCipher-encrypted SQLite |

## Policy Enforcement

Encryption is required by default (`PTVAULT_ENCRYPTION_REQUIRED` is on unless set to `0`, `false` or `no`):
- The "Disable Encryption" button is hidden and the API endpoint returns an error
- Encryption cannot be disabled without modifying the environment variable
- First-time setup always encrypts the database; if encryption fails, setup stops with an error and can be run again
- PTVault refuses to start with an unencrypted database that already has an account. To encrypt one, start once with `PTVAULT_ENCRYPTION_REQUIRED=0`, enable encryption in **Admin > Settings**, then restart without it
- Recommended for production deployments on shared systems

## Backup Recommendations

When encryption is enabled, include both the database and key files in backups:

```bash
# Backup all critical files
cp data/ptvault.db  backups/ptvault-$(date +%Y%m%d).db
cp data/ptvault.key backups/ptvault-$(date +%Y%m%d).key
cp data/ptvault.salt backups/ptvault-$(date +%Y%m%d).salt
```

Store backups in a separate, secure location from the main database.

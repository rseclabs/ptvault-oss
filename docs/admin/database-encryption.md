# Database Encryption

PTVault optionally encrypts the SQLite database using **SQLCipher**, providing AES-256 encryption at rest. This protects all engagement data, credentials, and evidence if the database file is accessed outside of PTVault.

## Requirements

Database encryption requires:
1. The `sqlcipher` system library
2. The `pysqlcipher3` Python package

Install these before enabling encryption:

```bash
# Debian / Ubuntu / Kali
sudo apt-get install -y sqlcipher libsqlcipher-dev python3-dev
pip install pysqlcipher3

# Fedora / RHEL
sudo dnf install -y sqlcipher sqlcipher-devel python3-devel
pip install pysqlcipher3
```

If these are not installed, the encryption option in Admin Settings shows as **Unavailable**.

## Checking Encryption Status

1. Go to **Admin > Settings**
2. Find the **Database Encryption** section

The status panel shows:

| Field | Description |
|-------|-------------|
| **Available** | Whether SQLCipher is installed |
| **Enabled** | Whether the current database is encrypted |
| **Key File Exists** | Whether the derived key file is present |
| **Salt File Exists** | Whether the salt file (for key derivation) is present |
| **Required by Policy** | Whether the `PTVAULT_ENCRYPTION_REQUIRED` env var prevents disabling |

## Enabling Encryption

1. Go to **Admin > Settings** → Database Encryption
2. Click **Enable Encryption**
3. Enter your **admin password** (used to derive the encryption key)
4. Click **Confirm**

PTVault will:
1. Derive an AES-256 key from your password using Argon2id + a random salt
2. Save the derived key to a key file (`data/ptvault.key`)
3. Save the salt to a salt file (`data/ptvault.salt`)
4. Encrypt the database file in-place using SQLCipher

The process takes a few seconds for typical database sizes. PTVault remains available throughout.

> **Important:** Store the key file and salt file securely. If both files are lost, the database cannot be decrypted.

## Disabling Encryption

1. Go to **Admin > Settings** → Database Encryption
2. Click **Disable Encryption**
3. Enter your admin password
4. Click **Confirm**

PTVault decrypts the database and removes the key/salt files.

> **Note:** Disabling encryption is blocked if the `PTVAULT_ENCRYPTION_REQUIRED` environment variable is set. This prevents accidental decryption in high-security environments.

## Key Recovery

If the key file is lost but the salt file is still present, you can re-derive the encryption key from your admin password:

1. Go to **Admin > Settings** → Database Encryption
2. Click **Recover Key**
3. Enter your admin password
4. PTVault re-derives the key and saves a new key file

If both the key file **and** the salt file are lost, the database **cannot be recovered** without brute-forcing the key. This is by design.

## Security Architecture

| Component | Details |
|-----------|---------|
| Encryption algorithm | AES-256 (via SQLCipher) |
| Key derivation | Argon2id (time_cost=3, memory=64MiB) + random 32-byte salt |
| Key storage | `data/ptvault.key` (derived key, not the password) |
| Salt storage | `data/ptvault.salt` |
| Database format | SQLCipher-encrypted SQLite |

## Policy Enforcement

For environments where encryption must always be active, set the environment variable:

```bash
export PTVAULT_ENCRYPTION_REQUIRED=1
```

With this variable set:
- The "Disable Encryption" button is hidden and the API endpoint returns an error
- Encryption cannot be disabled without modifying the environment variable
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

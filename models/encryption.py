"""
SQLCipher database encryption module for PTVault.

Provides transparent encryption for the SQLite database using SQLCipher.
When sqlcipher3 is installed, the database is encrypted at rest using
a 256-bit key derived from the user's master password via Argon2id.

If sqlcipher3 is not installed, falls back to plain sqlite3 (no encryption);
PTVAULT_ENCRYPTION_REQUIRED (on by default) makes startup refuse that instead.

The key is held in memory only (M-8). After setup it stays in this process;
after a restart the database is locked until unlock() is given the database
passphrase (the password chosen at setup), which re-derives the key from the
salt and checks it opens the database. A key file from older versions is
deleted on the first successful unlock. For unattended servers,
PTVAULT_DB_PASSPHRASE unlocks at startup and PTVAULT_STORE_KEY_FILE=1 keeps
writing the key file (anyone who can read it can open the database).
"""

import json
import logging
import os
import secrets
import shutil
import sqlite3
from datetime import datetime, timezone

from argon2.low_level import hash_secret_raw, Type

from config import Config

logger = logging.getLogger(__name__)

# Soft-import sqlcipher3 (preferred) or pysqlcipher3 (legacy fallback)
_SQLCIPHER_AVAILABLE = False
_sqlcipher = None

try:
    import sqlcipher3 as _sqlcipher
    _SQLCIPHER_AVAILABLE = True
except ImportError:
    try:
        from pysqlcipher3 import dbapi2 as _sqlcipher
        _SQLCIPHER_AVAILABLE = True
    except ImportError:
        pass


_SQLITE_HEADER = b'SQLite format 3\x00'
_unlocked_key = None     # the derived key, once setup or unlock() has run in this process


class DatabaseLocked(RuntimeError):
    """The database is encrypted and has not been unlocked in this process."""


class InvalidPassphrase(ValueError):
    """The passphrase does not open the database."""


def _encrypted_db_present():
    """True when the database file exists and is not a plaintext SQLite file (cheap header check)."""
    try:
        with open(Config.DATABASE_PATH, 'rb') as f:
            header = f.read(16)
    except OSError:
        return False
    return len(header) == 16 and header != _SQLITE_HEADER and os.path.exists(Config.ENCRYPTION_SALT_FILE)


def is_encryption_available():
    """Check if sqlcipher3 or pysqlcipher3 is installed and usable."""
    return _SQLCIPHER_AVAILABLE


def is_encryption_enabled():
    """Check if encryption is available and in use: the database is encrypted, or a
    key file is in use (PTVAULT_STORE_KEY_FILE). A key file on its own no longer
    counts (L-15): without the opt-in it is never read, so treating it as "enabled"
    made every connection ask for a key that could not be found."""
    return _SQLCIPHER_AVAILABLE and (_key_file_in_use() or _encrypted_db_present())


def retire_stray_key_file():
    """Set aside a key file that has no encrypted database to go with it (L-15).

    Called at startup. A key file is kept when PTVAULT_STORE_KEY_FILE is set, or
    when the database is encrypted (unlock() removes it once the passphrase is
    proven, M-8). Otherwise it is left over from an older version, for example
    after the database was deleted to start over: it is renamed, not deleted, in
    case it is still wanted. Returns the new path, or None.
    """
    path = Config.ENCRYPTION_KEY_FILE
    if not os.path.exists(path) or _key_file_in_use() or _encrypted_db_present():
        return None
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    moved = f'{path}.unused-{stamp}'
    os.replace(path, moved)
    logger.warning("Set aside %s: there is no encrypted database for it, so it was left by an older "
                   "version. It is now %s and can be deleted.", path, moved)
    return moved


def _key_file_in_use():
    """A key file is used only with the PTVAULT_STORE_KEY_FILE opt-in. Without it, a key
    file left by an older version is ignored, so the database asks for the passphrase
    once and unlock() then deletes the file (M-8)."""
    return getattr(Config, 'STORE_KEY_FILE', False) and os.path.exists(Config.ENCRYPTION_KEY_FILE)


def is_locked():
    """True when the database is encrypted and no key is available to this process."""
    return (_unlocked_key is None and _SQLCIPHER_AVAILABLE and not _key_file_in_use()
            and _encrypted_db_present())


def lock():
    """Forget the in-memory key (what a restart does; used by tests)."""
    global _unlocked_key
    _unlocked_key = None


def _remember_key(derived_key):
    """Keep the key in memory; write the key file only when explicitly configured."""
    global _unlocked_key
    _unlocked_key = derived_key
    if getattr(Config, 'STORE_KEY_FILE', False):
        _write_key_file(derived_key)


def _key_opens_database(key):
    try:
        conn = _sqlcipher.connect(Config.DATABASE_PATH)
        try:
            conn.execute(f"PRAGMA key = \"x'{key}'\"")
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            conn.close()
        return True
    except Exception:
        return False


def unlock(passphrase):
    """Re-derive the key from the passphrase and salt; keep it if it opens the database.

    Raises InvalidPassphrase otherwise. A key file left by an older version is
    removed once the passphrase is proven, unless PTVAULT_STORE_KEY_FILE is set.
    """
    if not _SQLCIPHER_AVAILABLE:
        raise RuntimeError("sqlcipher3 is not installed")
    try:
        salt = read_salt()
    except (OSError, ValueError):
        raise InvalidPassphrase("No encryption salt found")
    if not os.path.exists(Config.DATABASE_PATH) or os.path.getsize(Config.DATABASE_PATH) == 0:
        # SQLCipher would create an empty database here that any key "opens"
        raise InvalidPassphrase("There is no encrypted database to unlock")
    key = derive_key(passphrase or '', salt)
    if not _key_opens_database(key):
        raise InvalidPassphrase("The passphrase does not open the database")
    _remember_key(key)
    if not getattr(Config, 'STORE_KEY_FILE', False) and os.path.exists(Config.ENCRYPTION_KEY_FILE):
        os.remove(Config.ENCRYPTION_KEY_FILE)
        logger.warning("Removed the plaintext encryption key file; the key is now held in memory only")
    logger.info("Database unlocked")
    return key


def auto_unlock_from_env():
    """Unlock with PTVAULT_DB_PASSPHRASE if it is set. Returns True on success."""
    passphrase = os.environ.get('PTVAULT_DB_PASSPHRASE')
    if not passphrase or not is_locked():
        return False
    try:
        unlock(passphrase)
        return True
    except InvalidPassphrase:
        logger.error("PTVAULT_DB_PASSPHRASE does not open the database; it stays locked")
        return False


def derive_key(password, salt):
    """
    Derive a 256-bit encryption key from a password and salt using Argon2id.

    Uses the same parameters as PTVault's password hashing:
    time_cost=3, memory_cost=64MiB, parallelism=4, hash_len=32.

    Args:
        password: The master password string.
        salt: 16-byte salt value.

    Returns:
        str: 64 hex character string representing the 256-bit key.
    """
    raw = hash_secret_raw(
        secret=password.encode('utf-8'),
        salt=salt,
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        type=Type.ID
    )
    return raw.hex()


def generate_salt():
    """
    Generate a random 16-byte salt and write it to the salt file.

    Returns:
        bytes: The generated salt.
    """
    salt = secrets.token_bytes(16)
    salt_dir = os.path.dirname(Config.ENCRYPTION_SALT_FILE)
    if salt_dir and not os.path.exists(salt_dir):
        os.makedirs(salt_dir)

    with open(Config.ENCRYPTION_SALT_FILE, 'w') as f:
        f.write(salt.hex())

    os.chmod(Config.ENCRYPTION_SALT_FILE, 0o600)
    logger.info("Encryption salt generated and saved")
    return salt


def remove_stale_backups(db_path=None):
    """Remove backups left by an interrupted encrypt or decrypt; return how many (M-17).

    Either the transition finished (the backup is redundant) or it failed before
    replacing the database (the original is untouched), so a backup is never
    needed after the fact; a pre-encrypt backup is a full plaintext copy.
    """
    db_path = db_path or Config.DATABASE_PATH
    removed = 0
    for suffix in ('.backup_preencrypt', '.backup_predecrypt'):
        path = db_path + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
                removed += 1
                logger.warning("Removed %s, left by an interrupted encryption change", path)
            except OSError as e:
                logger.error("Could not remove %s: %s", path, e)
    return removed


def harden_database_permissions(db_path=None):
    """Make the database, its WAL/SHM files, the salt and any key file 0600 (M-14).

    SQLite creates files with the process umask (usually 0644), so another
    local user could copy the database. Errors are logged, not raised: a file
    owned by someone else should not stop the app.
    """
    db_path = db_path or Config.DATABASE_PATH
    for path in (db_path, db_path + '-wal', db_path + '-shm', db_path + '-journal',
                 Config.ENCRYPTION_SALT_FILE, Config.ENCRYPTION_KEY_FILE):
        try:
            if os.path.exists(path):
                os.chmod(path, 0o600)
        except OSError as e:
            logger.warning("Could not restrict permissions on %s: %s", path, e)


def read_salt():
    """
    Read the salt from the salt file.

    Returns:
        bytes: The salt value.

    Raises:
        FileNotFoundError: If the salt file doesn't exist.
    """
    with open(Config.ENCRYPTION_SALT_FILE, 'r') as f:
        return bytes.fromhex(f.read().strip())


def get_encryption_key():
    """
    The derived key: held in memory, or (legacy / PTVAULT_STORE_KEY_FILE) read
    from the key file.

    Returns:
        str: 64 hex character key string.

    Raises:
        DatabaseLocked: If no key is available (the database must be unlocked).
        ValueError: If the key file is malformed.
    """
    if _unlocked_key is not None:
        return _unlocked_key
    if not _key_file_in_use():
        raise DatabaseLocked("The database is locked; unlock it with the database passphrase")
    with open(Config.ENCRYPTION_KEY_FILE, 'r') as f:
        data = json.load(f)

    key = data.get('derived_key')
    if not key or len(key) != 64:
        raise ValueError("Invalid encryption key in key file")
    return key


def _write_key_file(derived_key):
    """
    Write the derived key to the key file with restricted permissions.

    Args:
        derived_key: 64 hex character key string.
    """
    key_dir = os.path.dirname(Config.ENCRYPTION_KEY_FILE)
    if key_dir and not os.path.exists(key_dir):
        os.makedirs(key_dir)

    data = {
        "version": 1,
        "kdf": "argon2id",
        "derived_key": derived_key,
        "created": datetime.now(timezone.utc).isoformat()
    }

    with open(Config.ENCRYPTION_KEY_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    os.chmod(Config.ENCRYPTION_KEY_FILE, 0o600)
    logger.info("Encryption key file written")


def setup_encryption(password):
    """
    Full encryption setup: generate salt, derive key, write key file,
    and migrate existing plaintext DB to encrypted.

    Called during first-time setup after the admin user is created.

    Args:
        password: The master password used for key derivation.
    """
    if not is_encryption_available():
        logger.warning("pysqlcipher3 not installed — skipping encryption setup")
        return

    salt = generate_salt()
    derived_key = derive_key(password, salt)

    # Migrate the DB first, passing the key directly. Only write the key
    # file after migration succeeds — otherwise a failed migration leaves
    # the key file behind and is_encryption_enabled() returns True while
    # the DB is still plaintext, breaking all subsequent connections.
    if os.path.exists(Config.DATABASE_PATH):
        try:
            _migrate_to_encrypted_with_key(Config.DATABASE_PATH, derived_key)
        except Exception as e:
            # Clean up salt file on failure (key file not written yet)
            if os.path.exists(Config.ENCRYPTION_SALT_FILE):
                os.remove(Config.ENCRYPTION_SALT_FILE)
            logger.error(f"Failed to migrate DB to encrypted: {e}")
            raise

    _remember_key(derived_key)
    logger.info("Encryption setup complete — salt file created, key held in memory")


def get_connection(db_path):
    """
    Get a database connection — encrypted (SQLCipher) or plain (sqlite3).

    This is the single entry point for all database connections in PTVault.
    Transparently returns an encrypted connection if encryption is enabled,
    or a plain sqlite3 connection otherwise.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A database connection (sqlcipher or sqlite3).
    """
    if not is_encryption_enabled():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    key = get_encryption_key()
    conn = _sqlcipher.connect(db_path)
    conn.row_factory = _sqlcipher.Row
    conn.execute(f"PRAGMA key = \"x'{key}'\"")
    # Verify the key works by reading the schema
    conn.execute("SELECT count(*) FROM sqlite_master")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _is_plaintext_db(db_path):
    """
    Check if a database file is a plaintext SQLite database.

    Args:
        db_path: Path to the database file.

    Returns:
        bool: True if the file is a readable plaintext SQLite DB with tables.
    """
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return False
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        conn.close()
        return result[0] >= 0  # Successfully read = plaintext
    except Exception:
        return False


def migrate_to_encrypted(db_path):
    """
    Migrate a plaintext SQLite database to an encrypted SQLCipher database.
    Reads the key from the key file.

    Args:
        db_path: Path to the plaintext database to encrypt.

    Raises:
        RuntimeError: If sqlcipher3 is not available or key file is missing.
    """
    if not is_encryption_available():
        raise RuntimeError("sqlcipher3 is not installed")

    key = get_encryption_key()   # DatabaseLocked if the key is not available
    _migrate_to_encrypted_with_key(db_path, key)


def _export_db(src_path, src_key, dst_path, dst_key):
    """
    Copy a whole database into a new file with SQLCipher's sqlcipher_export().

    sqlcipher_export() is SQLCipher's supported way to convert between
    plaintext and encrypted databases. Unlike replaying iterdump() output it
    recreates virtual tables (evidence_fts) properly instead of copying their
    shadow tables, so full-text search and its triggers survive the move.

    Args:
        src_path: Existing database to read.
        src_key: 64 hex char key for src_path, or None if it is plaintext.
        dst_path: New database file to create (must not exist).
        dst_key: 64 hex char key for dst_path, or None for plaintext.
    """
    conn = _sqlcipher.connect(src_path)
    try:
        if src_key:
            conn.execute(f"PRAGMA key = \"x'{src_key}'\"")
        conn.execute("SELECT count(*) FROM sqlite_master")  # verify key works
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        attach_key = f"x'{dst_key}'" if dst_key else ''
        conn.execute("ATTACH DATABASE ? AS export KEY ?", (dst_path, attach_key))
        conn.execute("SELECT sqlcipher_export('export')")
        conn.execute("DETACH DATABASE export")
    finally:
        conn.close()

    dst = _sqlcipher.connect(dst_path)
    try:
        if dst_key:
            dst.execute(f"PRAGMA key = \"x'{dst_key}'\"")
        dst.execute("PRAGMA journal_mode=WAL")
    finally:
        dst.close()


def _migrate_to_encrypted_with_key(db_path, key):
    """
    Migrate a plaintext SQLite database to an encrypted SQLCipher database
    using the provided key directly (no key file required).

    Args:
        db_path: Path to the plaintext database to encrypt.
        key: 64 hex character encryption key string.

    Raises:
        RuntimeError: If sqlcipher3 is not available.
    """
    if not is_encryption_available():
        raise RuntimeError("sqlcipher3 is not installed")

    if not _is_plaintext_db(db_path):
        logger.info("Database is already encrypted or empty — skipping migration")
        return
    backup_path = db_path + '.backup_preencrypt'
    encrypted_tmp = db_path + '.encrypted_tmp'

    # Back up the original (private: it is a full plaintext copy, M-17)
    shutil.copy2(db_path, backup_path)
    os.chmod(backup_path, 0o600)
    logger.info(f"Backed up plaintext DB to {backup_path}")

    swapped = False
    try:
        # Remove temp file if it exists from a previous failed attempt
        if os.path.exists(encrypted_tmp):
            os.remove(encrypted_tmp)

        _export_db(db_path, None, encrypted_tmp, key)

        # Remove WAL/SHM files from the old plaintext DB
        for suffix in ['-wal', '-shm']:
            wal_file = db_path + suffix
            if os.path.exists(wal_file):
                os.remove(wal_file)

        # Atomically replace the original with the encrypted version
        os.replace(encrypted_tmp, db_path)
        swapped = True
        harden_database_permissions(db_path)
        logger.info("Database successfully migrated to encrypted format")

        # The backup is a full plaintext copy of the data. Once the encrypted
        # file opens with the key, keep no unencrypted copy on disk.
        verify = _sqlcipher.connect(db_path)
        try:
            verify.execute(f"PRAGMA key = \"x'{key}'\"")
            verify.execute("SELECT count(*) FROM sqlite_master")
        finally:
            verify.close()
        os.remove(backup_path)
        logger.info("Removed plaintext backup after verifying encrypted database")

    except Exception as e:
        # Clean up temp file on failure
        if os.path.exists(encrypted_tmp):
            os.remove(encrypted_tmp)
        # Leave no plaintext copy behind (M-17). Before the swap the original is
        # untouched; after it, put the plaintext original back so the live file
        # is never left half-way (the caller still sees the error).
        if os.path.exists(backup_path):
            if swapped:
                os.replace(backup_path, db_path)
            else:
                os.remove(backup_path)
        logger.error(f"Encryption migration failed: {e}")
        raise


def migrate_to_plaintext(db_path):
    """
    Migrate an encrypted SQLCipher database back to plaintext SQLite.

    Copies the encrypted DB into a new plaintext file with sqlcipher_export().

    Args:
        db_path: Path to the encrypted database.

    Raises:
        RuntimeError: If sqlcipher3 is not available or key file is missing.
    """
    if not is_encryption_available():
        raise RuntimeError("sqlcipher3 is not installed")


    if _is_plaintext_db(db_path):
        logger.info("Database is already plaintext — nothing to do")
        return

    key = get_encryption_key()
    backup_path = db_path + '.backup_predecrypt'
    plaintext_tmp = db_path + '.plaintext_tmp'

    # Back up the encrypted original
    shutil.copy2(db_path, backup_path)
    logger.info(f"Backed up encrypted DB to {backup_path}")

    swapped = False
    try:
        if os.path.exists(plaintext_tmp):
            os.remove(plaintext_tmp)

        _export_db(db_path, key, plaintext_tmp, None)

        # Remove WAL/SHM files from encrypted DB
        for suffix in ['-wal', '-shm']:
            wal_file = db_path + suffix
            if os.path.exists(wal_file):
                os.remove(wal_file)

        os.replace(plaintext_tmp, db_path)
        swapped = True
        # The plaintext database is created with the umask; keep it private (M-17)
        harden_database_permissions(db_path)
        logger.info("Database successfully decrypted to plaintext format")
        os.remove(backup_path)

    except Exception as e:
        if os.path.exists(plaintext_tmp):
            os.remove(plaintext_tmp)
        if os.path.exists(backup_path):
            if swapped:
                os.replace(backup_path, db_path)      # back to the encrypted original
            else:
                os.remove(backup_path)
        logger.error(f"Decryption migration failed: {e}")
        raise


def disable_encryption():
    """
    Disable encryption: decrypt the database and remove key/salt files.

    Raises:
        RuntimeError: If encryption is not currently enabled.
    """
    if not is_encryption_enabled():
        raise RuntimeError("Encryption is not currently enabled")

    # Decrypt the database first
    migrate_to_plaintext(Config.DATABASE_PATH)

    # Remove key file and forget the key
    if os.path.exists(Config.ENCRYPTION_KEY_FILE):
        os.remove(Config.ENCRYPTION_KEY_FILE)
        logger.info("Removed encryption key file")
    lock()

    # Keep salt file — it's harmless and enables re-encryption later
    logger.info("Encryption disabled — database is now plaintext")


def check_and_migrate_if_needed(db_path):
    """
    Startup check: if encryption is enabled but the DB is still plaintext,
    migrate it to encrypted format.

    Args:
        db_path: Path to the database file.
    """
    if not is_encryption_enabled():
        return

    if not os.path.exists(db_path):
        return

    if _is_plaintext_db(db_path):
        logger.info("Encryption enabled but DB is plaintext — migrating...")
        migrate_to_encrypted(db_path)


def plaintext_database_refusal(db_path):
    """Return why startup must stop, or None (M-11).

    While encryption is required, a plaintext database that already holds an
    account is refused: setup has run, so the data on disk is unprotected. A
    plaintext database with no account is the normal state before setup, and
    an encrypted (or locked) one is fine.
    """
    if not getattr(Config, 'ENCRYPTION_REQUIRED', False) or not _is_plaintext_db(db_path):
        return None
    try:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        try:
            users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error:
        return None          # no users table yet: not set up
    if not users:
        return None
    return (f"The database {db_path} is not encrypted, but encryption is required "
            "(PTVAULT_ENCRYPTION_REQUIRED, on by default). To encrypt it, start once with "
            "PTVAULT_ENCRYPTION_REQUIRED=0, enable encryption in Admin > Settings, then restart "
            "without it. To keep it unencrypted, set PTVAULT_ENCRYPTION_REQUIRED=0.")

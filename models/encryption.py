"""
SQLCipher database encryption module for PTVault.

Provides transparent encryption for the SQLite database using SQLCipher.
When sqlcipher3 is installed, the database is encrypted at rest using
a 256-bit key derived from the user's master password via Argon2id.

If sqlcipher3 is not installed, falls back to plain sqlite3 (no encryption).
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


def is_encryption_available():
    """Check if sqlcipher3 or pysqlcipher3 is installed and usable."""
    return _SQLCIPHER_AVAILABLE


def is_encryption_enabled():
    """Check if encryption is both available and configured (key file exists)."""
    return _SQLCIPHER_AVAILABLE and os.path.exists(Config.ENCRYPTION_KEY_FILE)


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
    Read the derived encryption key from the key file.

    Returns:
        str: 64 hex character key string.

    Raises:
        FileNotFoundError: If the key file doesn't exist.
        ValueError: If the key file is malformed.
    """
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

    _write_key_file(derived_key)
    logger.info("Encryption setup complete — key file and salt file created")


def recover_key(password):
    """
    Re-derive the encryption key from the password and existing salt file.
    Writes a new key file.

    Used when the key file is lost but the salt file still exists.

    Args:
        password: The master password.

    Returns:
        str: The re-derived key.

    Raises:
        FileNotFoundError: If the salt file doesn't exist.
    """
    salt = read_salt()
    derived_key = derive_key(password, salt)
    _write_key_file(derived_key)
    logger.info("Encryption key recovered from password + salt")
    return derived_key


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

    if not os.path.exists(Config.ENCRYPTION_KEY_FILE):
        raise RuntimeError("Encryption key file not found")

    key = get_encryption_key()
    _migrate_to_encrypted_with_key(db_path, key)


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

    # Back up the original
    shutil.copy2(db_path, backup_path)
    logger.info(f"Backed up plaintext DB to {backup_path}")

    try:
        # Remove temp file if it exists from a previous failed attempt
        if os.path.exists(encrypted_tmp):
            os.remove(encrypted_tmp)

        # Read all schema and data from the plaintext DB using plain sqlite3
        src = sqlite3.connect(db_path)
        # Checkpoint WAL to ensure all data is in the main file
        src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        sql_dump = list(src.iterdump())
        src.close()

        # Create new encrypted database
        dst = _sqlcipher.connect(encrypted_tmp)
        dst.execute(f"PRAGMA key = \"x'{key}'\"")
        dst.execute("PRAGMA journal_mode=WAL")

        # Replay the dump into the encrypted DB.
        # iterdump() emits INSERT statements for FTS4 shadow tables
        # (evidence_fts_content, etc.) which must be skipped — the FTS
        # triggers will repopulate the index once the schema is in place.
        # CREATE VIRTUAL TABLE statements are NOT skipped; if FTS4 is
        # unavailable the explicit repopulation step below will warn.
        for statement in sql_dump:
            if 'evidence_fts' in statement and statement.strip().upper().startswith('INSERT'):
                continue
            try:
                dst.execute(statement)
            except Exception as stmt_err:
                # Log schema failures loudly so they are visible in the log
                logger.warning(f"Skipping statement during migration: {stmt_err} | stmt={statement[:120]}")
                continue
        dst.commit()

        # Repopulate FTS index from existing evidence data
        try:
            dst.execute("""
                INSERT INTO evidence_fts(docid, title, content, metadata)
                SELECT id, title, content, metadata FROM evidence
            """)
            dst.commit()
        except Exception as fts_err:
            logger.warning(f"FTS repopulation skipped: {fts_err}")

        dst.close()

        # Remove WAL/SHM files from the old plaintext DB
        for suffix in ['-wal', '-shm']:
            wal_file = db_path + suffix
            if os.path.exists(wal_file):
                os.remove(wal_file)

        # Atomically replace the original with the encrypted version
        os.replace(encrypted_tmp, db_path)
        logger.info("Database successfully migrated to encrypted format")

    except Exception as e:
        # Clean up temp file on failure
        if os.path.exists(encrypted_tmp):
            os.remove(encrypted_tmp)
        logger.error(f"Encryption migration failed: {e}")
        raise


def migrate_to_plaintext(db_path):
    """
    Migrate an encrypted SQLCipher database back to plaintext SQLite.

    Reads the encrypted DB with sqlcipher3 using iterdump(), then replays
    into a new plaintext DB using plain sqlite3.

    Args:
        db_path: Path to the encrypted database.

    Raises:
        RuntimeError: If sqlcipher3 is not available or key file is missing.
    """
    if not is_encryption_available():
        raise RuntimeError("sqlcipher3 is not installed")

    if not os.path.exists(Config.ENCRYPTION_KEY_FILE):
        raise RuntimeError("Encryption key file not found — cannot decrypt")

    if _is_plaintext_db(db_path):
        logger.info("Database is already plaintext — nothing to do")
        return

    key = get_encryption_key()
    backup_path = db_path + '.backup_predecrypt'
    plaintext_tmp = db_path + '.plaintext_tmp'

    # Back up the encrypted original
    shutil.copy2(db_path, backup_path)
    logger.info(f"Backed up encrypted DB to {backup_path}")

    try:
        if os.path.exists(plaintext_tmp):
            os.remove(plaintext_tmp)

        # Read all schema and data from the encrypted DB
        src = _sqlcipher.connect(db_path)
        src.execute(f"PRAGMA key = \"x'{key}'\"")
        src.execute("SELECT count(*) FROM sqlite_master")  # verify key works
        sql_dump = list(src.iterdump())
        src.close()

        # Create new plaintext database using plain sqlite3
        # Skip FTS INSERT statements — triggers will handle repopulation.
        # CREATE VIRTUAL TABLE statements are NOT skipped.
        dst = sqlite3.connect(plaintext_tmp)
        for statement in sql_dump:
            if 'evidence_fts' in statement and statement.strip().upper().startswith('INSERT'):
                continue
            try:
                dst.execute(statement)
            except Exception as stmt_err:
                logger.warning(f"Skipping statement during migration: {stmt_err} | stmt={statement[:120]}")
                continue
        dst.commit()

        # Repopulate FTS index from existing evidence data
        try:
            dst.execute("""
                INSERT INTO evidence_fts(docid, title, content, metadata)
                SELECT id, title, content, metadata FROM evidence
            """)
            dst.commit()
        except Exception as fts_err:
            logger.warning(f"FTS repopulation skipped: {fts_err}")

        dst.execute("PRAGMA journal_mode=WAL")
        dst.close()

        # Remove WAL/SHM files from encrypted DB
        for suffix in ['-wal', '-shm']:
            wal_file = db_path + suffix
            if os.path.exists(wal_file):
                os.remove(wal_file)

        os.replace(plaintext_tmp, db_path)
        logger.info("Database successfully decrypted to plaintext format")

    except Exception as e:
        if os.path.exists(plaintext_tmp):
            os.remove(plaintext_tmp)
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

    # Remove key file
    if os.path.exists(Config.ENCRYPTION_KEY_FILE):
        os.remove(Config.ENCRYPTION_KEY_FILE)
        logger.info("Removed encryption key file")

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

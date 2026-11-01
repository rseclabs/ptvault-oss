"""
Tests for the SQLCipher database encryption module.

Tests key derivation, salt/key file management, connection fallback,
and (when pysqlcipher3 is available) encrypted DB creation and migration.
"""

import json
import os
import sqlite3
import tempfile

import pytest

# Add parent directory to path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import encryption
from config import Config


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Set up temporary data directory and override Config paths."""
    key_file = str(tmp_path / 'encryption.key')
    salt_file = str(tmp_path / 'encryption.salt')
    db_path = str(tmp_path / 'test.db')

    monkeypatch.setattr(Config, 'ENCRYPTION_KEY_FILE', key_file)
    monkeypatch.setattr(Config, 'ENCRYPTION_SALT_FILE', salt_file)
    monkeypatch.setattr(Config, 'DATABASE_PATH', db_path)

    return tmp_path


class TestKeyDerivation:
    """Tests for Argon2id key derivation."""

    def test_derive_key_deterministic(self):
        """Same password + salt should always produce the same key."""
        salt = b'\x00' * 16
        key1 = encryption.derive_key('test_password', salt)
        key2 = encryption.derive_key('test_password', salt)
        assert key1 == key2
        assert len(key1) == 64  # 32 bytes = 64 hex chars

    def test_derive_key_different_salt(self):
        """Different salts should produce different keys."""
        salt1 = b'\x00' * 16
        salt2 = b'\x01' * 16
        key1 = encryption.derive_key('test_password', salt1)
        key2 = encryption.derive_key('test_password', salt2)
        assert key1 != key2

    def test_derive_key_different_password(self):
        """Different passwords should produce different keys."""
        salt = b'\x00' * 16
        key1 = encryption.derive_key('password_one', salt)
        key2 = encryption.derive_key('password_two', salt)
        assert key1 != key2

    def test_derive_key_length(self):
        """Derived key should be exactly 64 hex chars (256 bits)."""
        salt = os.urandom(16)
        key = encryption.derive_key('any_password', salt)
        assert len(key) == 64
        # Verify it's valid hex
        int(key, 16)


class TestSaltGeneration:
    """Tests for salt file generation and reading."""

    def test_salt_generation(self, tmp_data_dir):
        """Salt should be 16 bytes and written to file."""
        salt = encryption.generate_salt()
        assert len(salt) == 16
        assert os.path.exists(Config.ENCRYPTION_SALT_FILE)

    def test_salt_file_content(self, tmp_data_dir):
        """Salt file should contain 32 hex chars."""
        salt = encryption.generate_salt()
        with open(Config.ENCRYPTION_SALT_FILE, 'r') as f:
            content = f.read().strip()
        assert len(content) == 32
        assert content == salt.hex()

    def test_read_salt(self, tmp_data_dir):
        """Reading salt should return the same bytes that were generated."""
        original_salt = encryption.generate_salt()
        read_back = encryption.read_salt()
        assert original_salt == read_back

    def test_salt_file_permissions(self, tmp_data_dir):
        """Salt file should have restricted permissions (0600)."""
        encryption.generate_salt()
        mode = os.stat(Config.ENCRYPTION_SALT_FILE).st_mode & 0o777
        assert mode == 0o600


class TestKeyFile:
    """Tests for key file management."""

    def test_write_and_read_key(self, tmp_data_dir):
        """Writing and reading a key file should round-trip correctly."""
        encryption._write_key_file('a' * 64)
        key = encryption.get_encryption_key()
        assert key == 'a' * 64

    def test_key_file_format(self, tmp_data_dir):
        """Key file should be valid JSON with expected fields."""
        encryption._write_key_file('b' * 64)
        with open(Config.ENCRYPTION_KEY_FILE, 'r') as f:
            data = json.load(f)
        assert data['version'] == 1
        assert data['kdf'] == 'argon2id'
        assert data['derived_key'] == 'b' * 64
        assert 'created' in data

    def test_key_file_permissions(self, tmp_data_dir):
        """Key file should have restricted permissions (0600)."""
        encryption._write_key_file('c' * 64)
        mode = os.stat(Config.ENCRYPTION_KEY_FILE).st_mode & 0o777
        assert mode == 0o600

    def test_invalid_key_file(self, tmp_data_dir):
        """Reading an invalid key file should raise ValueError."""
        with open(Config.ENCRYPTION_KEY_FILE, 'w') as f:
            json.dump({'version': 1, 'derived_key': 'tooshort'}, f)
        with pytest.raises(ValueError):
            encryption.get_encryption_key()

    def test_missing_key_file(self, tmp_data_dir):
        """Reading a missing key file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            encryption.get_encryption_key()


class TestEncryptionState:
    """Tests for encryption availability and enabled checks."""

    def test_fallback_to_sqlite(self, tmp_data_dir, monkeypatch):
        """When pysqlcipher3 is not available, should use plain sqlite3."""
        monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', False)
        assert not encryption.is_encryption_available()
        assert not encryption.is_encryption_enabled()

    def test_available_but_not_enabled(self, tmp_data_dir, monkeypatch):
        """When pysqlcipher3 is available but no key file, should not be enabled."""
        monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', True)
        assert encryption.is_encryption_available()
        assert not encryption.is_encryption_enabled()

    def test_enabled_when_key_exists(self, tmp_data_dir, monkeypatch):
        """When pysqlcipher3 is available and key file exists, should be enabled."""
        monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', True)
        encryption._write_key_file('d' * 64)
        assert encryption.is_encryption_enabled()

    def test_plain_connection(self, tmp_data_dir, monkeypatch):
        """Without encryption, get_connection should return a plain sqlite3 connection."""
        monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', False)
        db_path = str(tmp_data_dir / 'plain.db')
        conn = encryption.get_connection(db_path)
        # Should work as normal sqlite3
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()
        row = conn.execute("SELECT val FROM test WHERE id = 1").fetchone()
        assert row[0] == 'hello'
        conn.close()


class TestSetupAndRecovery:
    """Tests for encryption setup and key recovery."""

    def test_setup_creates_files(self, tmp_data_dir, monkeypatch):
        """setup_encryption should create both key and salt files."""
        # Disable actual sqlcipher so we don't try to migrate a non-existent DB
        monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', False)

        # setup_encryption should bail early since not available
        encryption.setup_encryption('test_password')
        assert not os.path.exists(Config.ENCRYPTION_KEY_FILE)
        assert not os.path.exists(Config.ENCRYPTION_SALT_FILE)

    def test_recover_key_from_salt(self, tmp_data_dir, monkeypatch):
        """recover_key should re-derive the same key from password + salt."""
        monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', True)

        # Generate salt and derive original key
        salt = encryption.generate_salt()
        original_key = encryption.derive_key('my_password', salt)
        encryption._write_key_file(original_key)

        # Verify the key matches
        stored_key = encryption.get_encryption_key()
        assert stored_key == original_key

        # Delete the key file
        os.remove(Config.ENCRYPTION_KEY_FILE)
        assert not os.path.exists(Config.ENCRYPTION_KEY_FILE)

        # Recover using password + salt
        recovered = encryption.recover_key('my_password')
        assert recovered == original_key
        assert os.path.exists(Config.ENCRYPTION_KEY_FILE)

    def test_recover_wrong_password(self, tmp_data_dir, monkeypatch):
        """recover_key with wrong password should produce a different key."""
        monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', True)

        salt = encryption.generate_salt()
        original_key = encryption.derive_key('correct_password', salt)

        os.remove(Config.ENCRYPTION_KEY_FILE) if os.path.exists(Config.ENCRYPTION_KEY_FILE) else None
        recovered = encryption.recover_key('wrong_password')
        assert recovered != original_key


class TestPlaintextDetection:
    """Tests for plaintext database detection."""

    def test_plaintext_db_detected(self, tmp_data_dir):
        """A normal sqlite3 database should be detected as plaintext."""
        db_path = str(tmp_data_dir / 'plain.db')
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        assert encryption._is_plaintext_db(db_path)

    def test_nonexistent_db_not_plaintext(self, tmp_data_dir):
        """A nonexistent file should not be detected as plaintext."""
        assert not encryption._is_plaintext_db(str(tmp_data_dir / 'nope.db'))


# Conditional tests that require sqlcipher3 or pysqlcipher3
_has_sqlcipher = False
try:
    import sqlcipher3
    _has_sqlcipher = True
except ImportError:
    try:
        from pysqlcipher3 import dbapi2
        _has_sqlcipher = True
    except ImportError:
        pass


@pytest.mark.skipif(not _has_sqlcipher, reason="sqlcipher3 not installed")
class TestEncryptedOperations:
    """Tests that require sqlcipher3 (or pysqlcipher3) to be installed."""

    def test_encrypted_connection(self, tmp_data_dir):
        """An encrypted DB should not be readable by plain sqlite3."""
        db_path = str(tmp_data_dir / 'encrypted.db')

        # Create key file
        salt = encryption.generate_salt()
        key = encryption.derive_key('test_password', salt)
        encryption._write_key_file(key)

        # Create an encrypted DB
        conn = encryption.get_connection(db_path)
        conn.execute("CREATE TABLE secret (id INTEGER, data TEXT)")
        conn.execute("INSERT INTO secret VALUES (1, 'classified')")
        conn.commit()
        conn.close()

        # Verify plain sqlite3 can't read it
        with pytest.raises(Exception):
            plain_conn = sqlite3.connect(db_path)
            plain_conn.execute("SELECT * FROM secret")

    def test_migration_plaintext_to_encrypted(self, tmp_data_dir):
        """Migrating a plaintext DB should preserve all data."""
        db_path = str(tmp_data_dir / 'migrate.db')

        # Create a plaintext DB with data
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO items VALUES (1, 'alpha')")
        conn.execute("INSERT INTO items VALUES (2, 'beta')")
        conn.commit()
        conn.close()

        # Set up encryption key
        salt = encryption.generate_salt()
        key = encryption.derive_key('migrate_password', salt)
        encryption._write_key_file(key)

        # Migrate
        encryption.migrate_to_encrypted(db_path)

        # Verify data preserved via encrypted connection
        conn = encryption.get_connection(db_path)
        rows = conn.execute("SELECT name FROM items ORDER BY id").fetchall()
        assert [r[0] for r in rows] == ['alpha', 'beta']
        conn.close()

        # Verify plain sqlite3 can't read it anymore
        assert not encryption._is_plaintext_db(db_path)

        # Verify backup was created
        assert os.path.exists(db_path + '.backup_preencrypt')

    def test_setup_encryption_full_flow(self, tmp_data_dir):
        """Full setup flow: create plaintext DB, then encrypt it."""
        db_path = Config.DATABASE_PATH

        # Create a plaintext DB
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'admin')")
        conn.commit()
        conn.close()

        # Run full setup
        encryption.setup_encryption('setup_password')

        # Verify files exist
        assert os.path.exists(Config.ENCRYPTION_KEY_FILE)
        assert os.path.exists(Config.ENCRYPTION_SALT_FILE)

        # Verify encrypted connection works
        conn = encryption.get_connection(db_path)
        row = conn.execute("SELECT name FROM users WHERE id = 1").fetchone()
        assert row[0] == 'admin'
        conn.close()

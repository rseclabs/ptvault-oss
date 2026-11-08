"""A key file left by an older version (retest L-15).

Since M-8 the key file is read only with PTVAULT_STORE_KEY_FILE, but its mere
presence still counted as "encryption enabled". With a plaintext or missing
database (the old "start over" steps deleted only the database) every
connection then asked for a key and startup failed with DatabaseLocked, while
/unlock was never offered. Now "enabled" follows the database itself, and a
key file with no encrypted database to go with it is set aside with a log
line at startup.
"""

import json
import os

import pytest

from config import Config
from models import encryption

pytestmark = pytest.mark.skipif(not encryption.is_encryption_available(), reason='sqlcipher3 not installed')
PASSPHRASE = 'Setup-Passphrase-123'


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'DATABASE_PATH', str(tmp_path / 'ptvault.db'))
    monkeypatch.setattr(Config, 'ENCRYPTION_KEY_FILE', str(tmp_path / 'encryption.key'))
    monkeypatch.setattr(Config, 'ENCRYPTION_SALT_FILE', str(tmp_path / 'encryption.salt'))
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', False)
    encryption.lock()
    with open(Config.ENCRYPTION_KEY_FILE, 'w') as f:                  # what an older version left behind
        json.dump({'derived_key': 'ab' * 32}, f)
    yield tmp_path
    encryption.lock()


def _plaintext_db():
    conn = encryption.get_connection(Config.DATABASE_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS t (x TEXT)')
    conn.commit()
    conn.close()


def test_a_stray_key_file_does_not_make_a_missing_database_encrypted(data_dir):
    assert not encryption.is_encryption_enabled() and not encryption.is_locked()
    _plaintext_db()                                                    # init_db's first connection works
    with open(Config.DATABASE_PATH, 'rb') as f:
        assert f.read(16).startswith(b'SQLite format 3')


def test_a_stray_key_file_does_not_lock_a_plaintext_database(data_dir):
    os.rename(Config.ENCRYPTION_KEY_FILE, str(data_dir / 'hold'))
    _plaintext_db()
    os.rename(str(data_dir / 'hold'), Config.ENCRYPTION_KEY_FILE)
    assert not encryption.is_encryption_enabled() and not encryption.is_locked()
    _plaintext_db()


def test_startup_sets_a_stray_key_file_aside(data_dir, caplog):
    moved = encryption.retire_stray_key_file()
    assert moved and os.path.exists(moved) and not os.path.exists(Config.ENCRYPTION_KEY_FILE)
    assert os.path.dirname(moved) == str(data_dir)
    assert 'encryption.key' in caplog.text
    assert encryption.retire_stray_key_file() is None                  # nothing left to do


def test_startup_keeps_a_key_file_that_goes_with_an_encrypted_database(data_dir):
    os.remove(Config.ENCRYPTION_KEY_FILE)
    _plaintext_db()
    encryption.setup_encryption(PASSPHRASE)
    encryption._write_key_file(encryption.get_encryption_key())        # an install from before M-8
    encryption.lock()
    assert encryption.retire_stray_key_file() is None                  # unlock() removes it after the passphrase
    assert os.path.exists(Config.ENCRYPTION_KEY_FILE) and encryption.is_locked()


def test_startup_keeps_an_opted_in_key_file(data_dir, monkeypatch):
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', True)
    assert encryption.retire_stray_key_file() is None
    assert os.path.exists(Config.ENCRYPTION_KEY_FILE)

"""No plaintext copy of the database outlives an encryption transition (retest 2: M-17).

A failed encrypt kept ptvault.db.backup_preencrypt, a full plaintext copy
(mode 0644); after disabling encryption the database was 0644 and
backup_predecrypt stayed forever.
"""

import os
import sqlite3
import stat

import pytest

from config import Config
from models import encryption

pytestmark = pytest.mark.skipif(not encryption.is_encryption_available(), reason='sqlcipher3 not installed')
PASSPHRASE = 'Backup-Passphrase-123'


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'DATABASE_PATH', str(tmp_path / 'p.db'))
    monkeypatch.setattr(Config, 'ENCRYPTION_KEY_FILE', str(tmp_path / 'k'))
    monkeypatch.setattr(Config, 'ENCRYPTION_SALT_FILE', str(tmp_path / 's'))
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', False)
    encryption.lock()
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.execute('CREATE TABLE t (x TEXT)')
    conn.execute("INSERT INTO t VALUES ('CLIENT-SECRET')")
    conn.commit()
    conn.close()
    yield tmp_path
    encryption.lock()


def _backups(folder):
    return sorted(p.name for p in folder.iterdir() if '.backup_' in p.name)


def _is_plaintext():
    with open(Config.DATABASE_PATH, 'rb') as f:
        return f.read(16).startswith(b'SQLite format 3')


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_a_failed_encrypt_leaves_no_plaintext_backup(db, monkeypatch):
    def broken(*args):
        raise OSError('disk full')
    monkeypatch.setattr(encryption, '_export_db', broken)
    with pytest.raises(OSError):
        encryption.setup_encryption(PASSPHRASE)
    assert _backups(db) == [] and _is_plaintext()


def test_a_failure_after_the_swap_puts_the_plaintext_original_back(db, monkeypatch):
    def broken(path=None):
        raise OSError('chmod refused')
    monkeypatch.setattr(encryption, 'harden_database_permissions', broken)
    with pytest.raises(OSError):
        encryption.setup_encryption(PASSPHRASE)
    assert _backups(db) == [] and _is_plaintext()
    conn = sqlite3.connect(Config.DATABASE_PATH)
    assert conn.execute('SELECT x FROM t').fetchone()[0] == 'CLIENT-SECRET'       # the original, intact
    conn.close()


def test_disabling_leaves_a_private_database_and_no_backup(db):
    encryption.setup_encryption(PASSPHRASE)
    assert _backups(db) == [] and _mode(Config.DATABASE_PATH) == 0o600
    encryption.disable_encryption()
    assert _is_plaintext()
    assert _backups(db) == [] and _mode(Config.DATABASE_PATH) == 0o600


def test_startup_removes_backups_left_by_an_interrupted_transition(db):
    for suffix in ('.backup_preencrypt', '.backup_predecrypt'):
        with open(Config.DATABASE_PATH + suffix, 'w') as f:
            f.write('left behind')
    assert encryption.remove_stale_backups() == 2
    assert _backups(db) == []

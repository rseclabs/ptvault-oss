"""M-8: the database key is held in memory, not written beside the database.

After setup the derived key stays in memory only; after a restart the
database is locked until someone enters the database passphrase (the setup
password). A legacy key file is removed on the first successful unlock.
Unattended servers can opt in to PTVAULT_DB_PASSPHRASE or
PTVAULT_STORE_KEY_FILE. PTVAULT_ENCRYPTION_REQUIRED defaults to on.
"""

import os

import pytest
from flask import Flask

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
    monkeypatch.delenv('PTVAULT_DB_PASSPHRASE', raising=False)
    encryption.lock()
    conn = encryption.get_connection(Config.DATABASE_PATH)        # plaintext database with a table
    conn.execute('CREATE TABLE t (x TEXT)')
    conn.execute("INSERT INTO t VALUES ('secret row')")
    conn.commit()
    conn.close()
    yield tmp_path
    encryption.lock()


def _read_row():
    conn = encryption.get_connection(Config.DATABASE_PATH)
    try:
        return conn.execute('SELECT x FROM t').fetchone()[0]
    finally:
        conn.close()


def _restart():
    encryption.lock()   # what a process restart does to the in-memory key


def test_setup_keeps_the_key_off_disk(data_dir):
    encryption.setup_encryption(PASSPHRASE)
    assert not os.path.exists(Config.ENCRYPTION_KEY_FILE)
    assert os.path.exists(Config.ENCRYPTION_SALT_FILE)
    with open(Config.DATABASE_PATH, 'rb') as f:
        assert not f.read(16).startswith(b'SQLite format 3')      # encrypted on disk
    assert _read_row() == 'secret row' and not encryption.is_locked()


def test_after_a_restart_the_database_is_locked_until_unlocked(data_dir):
    encryption.setup_encryption(PASSPHRASE)
    _restart()
    assert encryption.is_encryption_enabled() and encryption.is_locked()
    with pytest.raises(encryption.DatabaseLocked):
        encryption.get_connection(Config.DATABASE_PATH)

    with pytest.raises(encryption.InvalidPassphrase):
        encryption.unlock('wrong passphrase')
    assert encryption.is_locked()

    encryption.unlock(PASSPHRASE)
    assert not encryption.is_locked() and _read_row() == 'secret row'
    assert not os.path.exists(Config.ENCRYPTION_KEY_FILE)


def test_a_legacy_key_file_is_removed_on_the_first_successful_unlock(data_dir, monkeypatch):
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', True)
    encryption.setup_encryption(PASSPHRASE)                       # an install from before this change
    assert os.path.exists(Config.ENCRYPTION_KEY_FILE)
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', False)
    _restart()
    assert encryption.is_locked()                                 # the old file is not trusted any more
    with pytest.raises(encryption.DatabaseLocked):
        encryption.get_connection(Config.DATABASE_PATH)
    with pytest.raises(encryption.InvalidPassphrase):
        encryption.unlock('wrong passphrase')
    assert os.path.exists(Config.ENCRYPTION_KEY_FILE)             # a failed attempt removes nothing
    encryption.unlock(PASSPHRASE)
    assert not os.path.exists(Config.ENCRYPTION_KEY_FILE)
    _restart()
    assert encryption.is_locked()


def test_opt_in_key_file_survives_restarts(data_dir, monkeypatch):
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', True)
    encryption.setup_encryption(PASSPHRASE)
    _restart()
    assert not encryption.is_locked() and _read_row() == 'secret row'


def test_passphrase_from_the_environment_unlocks_at_start(data_dir, monkeypatch):
    encryption.setup_encryption(PASSPHRASE)
    _restart()
    monkeypatch.setenv('PTVAULT_DB_PASSPHRASE', PASSPHRASE)
    assert encryption.auto_unlock_from_env() is True
    assert not encryption.is_locked()
    _restart()
    monkeypatch.setenv('PTVAULT_DB_PASSPHRASE', 'wrong')
    assert encryption.auto_unlock_from_env() is False and encryption.is_locked()


# ------------------------------------------------------------------ the web side

@pytest.fixture
def gated_app(data_dir):
    from utils.unlock import locked_gate, unlock_bp
    from utils.csrf import csrf_protect
    encryption.setup_encryption(PASSPHRASE)
    _restart()
    app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates'))
    app.config['SECRET_KEY'] = 'k' * 32
    app.before_request(locked_gate)
    app.before_request(csrf_protect)
    app.register_blueprint(unlock_bp)
    app.add_url_rule('/dashboard', 'dashboard', lambda: 'dash')
    app.add_url_rule('/api/thing', 'thing', lambda: {'ok': True})
    app.add_url_rule('/api/health', 'health', lambda: {'status': 'ok'})
    return app.test_client()


def test_locked_app_sends_pages_to_unlock_and_refuses_the_api(gated_app):
    assert gated_app.get('/dashboard').headers['Location'].endswith('/unlock')
    resp = gated_app.get('/api/thing')
    assert resp.status_code == 503 and resp.get_json()['error'] == 'database_locked'
    assert gated_app.get('/api/health').status_code == 200
    assert gated_app.get('/unlock').status_code == 200


def _post_unlock(client, passphrase):
    client.set_cookie('csrf_token', 'c' * 64)
    return client.post('/api/unlock', json={'passphrase': passphrase}, headers={'X-CSRF-Token': 'c' * 64})


def test_unlock_endpoint(gated_app):
    assert gated_app.post('/api/unlock', json={'passphrase': PASSPHRASE}).status_code == 403   # CSRF
    assert _post_unlock(gated_app, 'wrong').status_code == 401
    assert encryption.is_locked()
    assert _post_unlock(gated_app, PASSPHRASE).status_code == 200
    assert not encryption.is_locked()
    assert gated_app.get('/api/thing').status_code == 200
    assert gated_app.get('/unlock').headers.get('Location', '').endswith('/')    # nothing left to unlock


# ------------------------------------------------------------------ PTVAULT_ENCRYPTION_REQUIRED

@pytest.mark.parametrize('value, expected', [
    (None, True), ('', True), ('1', True), ('true', True), ('YES', True), ('0', False), ('false', False), ('no', False),
])
def test_encryption_required_defaults_on(monkeypatch, value, expected):
    from config import encryption_required
    if value is None:
        monkeypatch.delenv('PTVAULT_ENCRYPTION_REQUIRED', raising=False)
    else:
        monkeypatch.setenv('PTVAULT_ENCRYPTION_REQUIRED', value)
    assert encryption_required() is expected

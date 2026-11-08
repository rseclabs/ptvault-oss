"""First-time setup on an encrypted install (retest L-13, M-11).

L-13: setup encrypts the database and then records the auto-login session;
the session row must land in the encrypted database, or the setup cookie is
refused with "session revoked" on the first request.
"""

import os
import sqlite3

import pytest
from flask import Flask, g

from models import encryption

pytestmark = pytest.mark.skipif(not encryption.is_encryption_available(), reason='sqlcipher3 not installed')
PASSWORD = 'Setup-Passphrase-123'
CSRF = 'c' * 64


@pytest.fixture
def fresh_app(tmp_path, monkeypatch):
    from config import BASE_DIR, Config
    from features import register_blueprints
    from tests.conftest import _init_test_db
    from utils.csrf import csrf_protect

    monkeypatch.setattr(Config, 'DATABASE_PATH', str(tmp_path / 'ptvault.db'))
    monkeypatch.setattr(Config, 'ENCRYPTION_KEY_FILE', str(tmp_path / 'encryption.key'))
    monkeypatch.setattr(Config, 'ENCRYPTION_SALT_FILE', str(tmp_path / 'encryption.salt'))
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path / 'uploads'))
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', False)
    encryption.lock()

    conn = sqlite3.connect(Config.DATABASE_PATH)
    _init_test_db(conn)
    conn.close()

    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
    app.config['SECRET_KEY'] = 'setup-encryption-test-secret-key-0123456789'
    app.config['TESTING'] = True
    import importlib
    from features import BLUEPRINTS
    for module_path, _ in BLUEPRINTS:
        importlib.reload(importlib.import_module(module_path))
    app.before_request(csrf_protect)
    register_blueprints(app)

    @app.teardown_appcontext
    def close_db(error):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    yield app
    encryption.lock()


def _setup(client, **extra):
    client.set_cookie('csrf_token', CSRF)
    body = {'email': 'admin@example.com', 'password': PASSWORD, 'full_name': 'Admin', **extra}
    return client.post('/api/auth/setup', json=body, headers={'X-CSRF-Token': CSRF})


def test_setup_cookie_works_on_an_encrypted_install(fresh_app):
    from config import Config
    client = fresh_app.test_client()
    resp = _setup(client)
    assert resp.status_code == 201, resp.get_json()
    with open(Config.DATABASE_PATH, 'rb') as f:
        assert not f.read(16).startswith(b'SQLite format 3')      # setup encrypted it

    resp = client.get('/api/engagements')
    assert resp.status_code == 200, resp.get_json()


# ------------------------------------------------------------------ M-11
# While encryption is required (the default), setup cannot leave the database
# plaintext: the request cannot opt out, and a failed encryption fails setup and
# removes the admin it created, so setup can simply be run again.

def _is_encrypted():
    from config import Config
    with open(Config.DATABASE_PATH, 'rb') as f:
        return not f.read(16).startswith(b'SQLite format 3')


def _user_count():
    from config import Config
    conn = encryption.get_connection(Config.DATABASE_PATH)
    try:
        return conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    finally:
        conn.close()


def test_required_encryption_ignores_the_opt_out(fresh_app, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', True)
    resp = _setup(fresh_app.test_client(), enable_encryption=False)
    assert resp.status_code == 201, resp.get_json()
    assert _is_encrypted()


def test_a_failed_encryption_fails_setup_and_removes_the_admin(fresh_app, monkeypatch):
    from config import Config
    import routes.auth
    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', True)

    def broken(password):
        raise OSError('disk full')
    monkeypatch.setattr(routes.auth, 'setup_encryption', broken)
    client = fresh_app.test_client()
    resp = _setup(client)
    assert resp.status_code == 500
    assert 'encrypt' in resp.get_json()['error'].lower()
    assert 'auth_token' not in resp.headers.get('Set-Cookie', '')
    assert not _is_encrypted() and _user_count() == 0

    monkeypatch.setattr(routes.auth, 'setup_encryption', encryption.setup_encryption)
    assert _setup(client).status_code == 201                    # setup can be run again
    assert _is_encrypted() and _user_count() == 1


def test_opt_out_still_works_when_encryption_is_not_required(fresh_app, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', False)
    assert _setup(fresh_app.test_client(), enable_encryption=False).status_code == 201
    assert not _is_encrypted()


def test_startup_refuses_a_plaintext_database_in_use_while_required(fresh_app, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', True)
    assert encryption.plaintext_database_refusal(Config.DATABASE_PATH) is None      # before setup: fine

    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', False)
    assert _setup(fresh_app.test_client(), enable_encryption=False).status_code == 201
    assert encryption.plaintext_database_refusal(Config.DATABASE_PATH) is None      # not required: fine

    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', True)
    message = encryption.plaintext_database_refusal(Config.DATABASE_PATH)
    assert message and 'PTVAULT_ENCRYPTION_REQUIRED' in message


def test_startup_accepts_an_encrypted_database(fresh_app, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', True)
    assert _setup(fresh_app.test_client()).status_code == 201
    assert encryption.plaintext_database_refusal(Config.DATABASE_PATH) is None
    encryption.lock()
    assert encryption.plaintext_database_refusal(Config.DATABASE_PATH) is None      # locked is not plaintext


# ------------------------------------------------------------------ M-14

def test_evidence_files_follow_the_database_encryption(fresh_app, monkeypatch):
    """Uploads are encrypted with the database key, survive a restart and unlock, are
    decrypted when encryption is disabled and encrypted again when it is enabled."""
    import io
    import stat
    from config import Config
    from models import upload_store
    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', False)       # so it can be disabled below
    client = fresh_app.test_client()
    assert _setup(client).status_code == 201
    token = client.get_cookie('csrf_token').value
    headers = {'X-CSRF-Token': token}

    engagement = client.post('/api/engagements', json={'name': 'E'}, headers=headers).get_json()
    assert client.post('/api/engagements/active', json={'engagement_id': engagement['id']},
                       headers=headers).status_code == 200
    secret = b'Hunter2-ACME loot'
    ev = client.post('/api/evidence', data={'evidence_type': 'other', 'title': 't',
                                            'file': (io.BytesIO(secret), 'loot.txt')},
                     content_type='multipart/form-data', headers=headers).get_json()
    conn = encryption.get_connection(Config.DATABASE_PATH)
    rel = conn.execute('SELECT file_path FROM evidence WHERE id = ?', (ev['id'],)).fetchone()[0]
    conn.close()
    path = os.path.join(Config.UPLOAD_FOLDER, rel)

    def on_disk():
        with open(path, 'rb') as f:
            return f.read()

    def downloaded():
        resp = client.get(f"/api/evidence/{ev['id']}/download")
        assert resp.status_code == 200, resp.get_json()
        return resp.data

    assert secret not in on_disk() and on_disk().startswith(upload_store.MAGIC)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert downloaded() == secret

    encryption.lock()                                                  # a restart
    with pytest.raises(encryption.DatabaseLocked):
        upload_store.read_file(path, rel)
    encryption.unlock(PASSWORD)
    assert downloaded() == secret

    assert client.post('/api/admin/encryption/disable', json={}, headers=headers).status_code == 200
    assert on_disk() == secret and downloaded() == secret

    resp = client.post('/api/admin/encryption/enable', json={'password': PASSWORD}, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    assert on_disk().startswith(upload_store.MAGIC) and downloaded() == secret


# ------------------------------------------------------------------ retest 2: L-33

def test_a_key_file_that_cannot_be_written_does_not_undo_an_encrypted_setup(fresh_app, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, 'ENCRYPTION_REQUIRED', True)
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', True)

    def unwritable(key):
        raise OSError('read-only key folder')
    monkeypatch.setattr(encryption, '_write_key_file', unwritable)
    client = fresh_app.test_client()
    resp = _setup(client)
    assert resp.status_code == 201, resp.get_json()
    assert _is_encrypted() and _user_count() == 1
    assert client.get('/api/engagements').status_code == 200


def test_setup_encryption_never_replaces_the_salt_of_an_encrypted_database(fresh_app):
    from config import Config
    encryption.setup_encryption(PASSWORD)
    salt = open(Config.ENCRYPTION_SALT_FILE).read()
    with pytest.raises(RuntimeError):
        encryption.setup_encryption('Another-Passphrase-123')
    assert open(Config.ENCRYPTION_SALT_FILE).read() == salt
    encryption.lock()
    encryption.unlock(PASSWORD)                                       # still opens with the first passphrase

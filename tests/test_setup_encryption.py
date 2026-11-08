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

"""Enabling encryption from Admin > Settings (retest M-12).

The passphrase is the only protection for the database key (M-8), so the
enable route applies the same policy as setup: 12+ characters with upper and
lower case letters and a digit.
"""

import pytest

from models import encryption

STRONG = 'Enable-Passphrase-123'


@pytest.fixture
def enable(live_app, monkeypatch):
    """POST /api/admin/encryption/enable as admin; records what would be encrypted."""
    calls = []
    monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', True)
    monkeypatch.setattr(encryption, 'setup_encryption', calls.append)
    client = live_app.client_for('admin')

    def post(body):
        return client.post('/api/admin/encryption/enable', json=body)
    post.calls = calls
    return post


@pytest.mark.parametrize('password', ['a', 'short-Pass1', 'alllowercase-123', 'ALLUPPERCASE-123',
                                      'No-Digits-Here-At-All', '', 12345678901234, ['Enable-Passphrase-123']])
def test_a_weak_or_malformed_passphrase_is_refused(enable, password):
    resp = enable({'password': password})
    assert resp.status_code == 400, resp.get_json()
    assert enable.calls == []                                   # nothing was encrypted


def test_a_strong_passphrase_enables_encryption(enable):
    resp = enable({'password': STRONG})
    assert resp.status_code == 200, resp.get_json()
    assert enable.calls == [STRONG]


# ------------------------------------------------------------------ L-16
# The admin encryption routes describe what actually happens: the key is held
# in memory unless PTVAULT_STORE_KEY_FILE is set, and unlocking is done at
# /unlock (the old recover route re-ran unlock and claimed to save a key file).

def test_enable_reports_where_the_key_is_kept(enable, live_app):
    body = enable({'password': STRONG}).get_json()
    assert body['key_storage'] == 'memory' and 'key_file' not in body

    conn = live_app.db()
    details = conn.execute("SELECT details FROM audit_log WHERE action = 'encryption_enable'").fetchone()[0]
    conn.close()
    assert 'memory' in details and 'encryption.key' not in details and 'no.key' not in details


def test_enable_names_the_key_file_only_when_one_is_written(enable, monkeypatch):
    from config import Config
    monkeypatch.setattr(Config, 'STORE_KEY_FILE', True)
    body = enable({'password': STRONG}).get_json()
    assert body['key_storage'] == 'file' and body['key_file'] == Config.ENCRYPTION_KEY_FILE


def test_the_recover_route_is_gone(live_app):
    client = live_app.client_for('admin')
    assert client.post('/api/admin/encryption/recover', json={'password': STRONG}).status_code == 404
    assert not hasattr(encryption, 'recover_key')

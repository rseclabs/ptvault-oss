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

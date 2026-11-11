"""CSRF failures caused by plain http in production say so.

With ENVIRONMENT=production PTVault's cookies are Secure, and PTVault serves only
http, so a browser at http://<server-ip> drops them and the first login failed
with a bare "CSRF token missing". The request is still refused; only the
message changes, and only when Secure cookies are what went missing.
"""

import pytest
from flask import Flask, jsonify

from config import Config
from utils.csrf import INSECURE_COOKIE_HINT, csrf_protect


@pytest.fixture
def client():
    app = Flask(__name__)
    app.before_request(csrf_protect)

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        return jsonify({'ok': True})
    return app.test_client()


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(Config, 'ENVIRONMENT', 'production')


def _login(client, base_url, headers=None):
    return client.post('/api/auth/login', json={}, base_url=base_url,
                       headers={'X-CSRF-Token': 'a' * 64, **(headers or {})})


def test_plain_http_to_a_server_address_explains_tls(client, production):
    resp = _login(client, 'http://192.168.1.20:5000')
    assert resp.status_code == 403
    error = resp.get_json()['error']
    assert error == INSECURE_COOKIE_HINT
    assert error.startswith('CSRF token missing')       # the front end retries on this prefix
    assert 'https' in error and 'nginx' in error


@pytest.mark.parametrize('base_url', ['http://localhost:5000', 'http://127.0.0.1:5000',
                                      'http://[::1]:5000', 'https://ptvault.example.com'])
def test_no_hint_where_browsers_send_secure_cookies(client, production, base_url):
    resp = _login(client, base_url)
    assert resp.status_code == 403
    assert resp.get_json()['error'] == 'CSRF token missing'


def test_no_hint_behind_a_tls_proxy(client, production):
    resp = _login(client, 'http://10.0.0.5:5000', headers={'X-Forwarded-Proto': 'https'})
    assert resp.get_json()['error'] == 'CSRF token missing'


def test_no_hint_in_development(client, monkeypatch):
    monkeypatch.setattr(Config, 'ENVIRONMENT', 'development')    # cookies are not Secure there
    resp = _login(client, 'http://192.168.1.20:5000')
    assert resp.get_json()['error'] == 'CSRF token missing'


def test_no_hint_when_the_cookie_arrived(client, production):
    client.set_cookie('csrf_token', 'b' * 64, domain='192.168.1.20')
    resp = _login(client, 'http://192.168.1.20:5000')
    assert resp.status_code == 403
    assert resp.get_json()['error'] == 'CSRF token mismatch'


def test_matching_tokens_still_pass(client, production):
    client.set_cookie('csrf_token', 'a' * 64, domain='192.168.1.20')
    assert _login(client, 'http://192.168.1.20:5000').status_code == 200

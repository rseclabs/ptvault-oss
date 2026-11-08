"""M-5: CyberChef install is admin-only, pinned, verified, and served sandboxed.

Install/update fetch one pinned release asset and check its SHA-256 and size
before anything on disk changes; zip entries cannot escape the install
folder; a failed install leaves the existing one in place; two installs
cannot run at once. CyberChef pages get a sandbox CSP, so its code (which
needs unsafe-eval) runs in an opaque origin without the user's session.
"""

import hashlib
import io
import zipfile

import pytest

from tests.conftest import ENGAGEMENT_A


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, body in entries.items():
            z.writestr(name, body)
    return buf.getvalue()


GOOD = _zip({'CyberChef_v11.5.0.html': '<html>new</html>', 'assets/main.js': 'x'})


class _FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]


@pytest.fixture
def cc(live_app, tmp_path, monkeypatch):
    import routes.admin as admin
    tools = tmp_path / 'tools'
    existing = tools / 'cyberchef'
    existing.mkdir(parents=True)
    (existing / 'CyberChef_v11.4.0.html').write_text('<html>old</html>')
    monkeypatch.setattr(admin, 'TOOLS_DIR', str(tools))
    monkeypatch.setattr(admin, 'CYBERCHEF_DIR', str(existing))
    monkeypatch.setattr(admin, 'CYBERCHEF_VERSION_FILE', str(existing / 'version.json'))
    monkeypatch.setattr(admin, 'CYBERCHEF_SHA256', hashlib.sha256(GOOD).hexdigest())

    requested = []

    def fake_get(url, **kwargs):
        requested.append(url)
        return _FakeResponse(live_app.download_body)

    monkeypatch.setattr(admin.requests, 'get', fake_get)
    live_app.download_body = GOOD
    live_app.requested, live_app.admin_module, live_app.cc_dir = requested, admin, existing
    return live_app


def _post(live, user, path):
    return live.client_for(user, active_engagement=ENGAGEMENT_A).post(f'/api/admin/cyberchef/{path}')


@pytest.mark.parametrize('path', ['install', 'update'])
@pytest.mark.parametrize('user', ['editor', 'viewer', 'owner'])
def test_non_admins_cannot_install(cc, user, path):
    assert _post(cc, user, path).status_code == 403
    assert cc.requested == []


def test_non_admins_cannot_trigger_update_checks(cc):
    resp = cc.client_for('editor').get('/api/admin/cyberchef/check-update')
    assert resp.status_code == 403


def test_install_fetches_only_the_pinned_asset_and_verifies_it(cc):
    resp = _post(cc, 'admin', 'install')
    assert resp.status_code == 200, resp.get_json()
    assert cc.requested == [cc.admin_module.CYBERCHEF_URL]
    assert 'releases/latest' not in cc.admin_module.CYBERCHEF_URL
    assert (cc.cc_dir / 'CyberChef_v11.5.0.html').read_text() == '<html>new</html>'
    assert not (cc.cc_dir / 'CyberChef_v11.4.0.html').exists()
    assert resp.get_json()['version'] == cc.admin_module.CYBERCHEF_VERSION


def test_tampered_download_changes_nothing(cc):
    cc.download_body = _zip({'CyberChef_v11.5.0.html': '<script>evil()</script>'})
    resp = _post(cc, 'admin', 'install')
    assert resp.status_code == 502
    assert (cc.cc_dir / 'CyberChef_v11.4.0.html').read_text() == '<html>old</html>'


def test_oversized_download_is_refused(cc, monkeypatch):
    monkeypatch.setattr(cc.admin_module, 'CYBERCHEF_MAX_BYTES', 100)
    assert _post(cc, 'admin', 'install').status_code == 502
    assert (cc.cc_dir / 'CyberChef_v11.4.0.html').exists()


@pytest.mark.parametrize('bad_name', ['../escaped.html', '/abs/escaped.html', 'assets/../../escaped.html'])
def test_zip_entries_cannot_escape_the_install_folder(cc, monkeypatch, bad_name):
    body = _zip({'CyberChef_v11.5.0.html': 'x', bad_name: 'pwned'})
    cc.download_body = body
    monkeypatch.setattr(cc.admin_module, 'CYBERCHEF_SHA256', hashlib.sha256(body).hexdigest())
    assert _post(cc, 'admin', 'install').status_code == 502
    tools = cc.cc_dir.parent
    assert not any(p.name == 'escaped.html' for p in tools.parent.rglob('escaped.html'))
    assert (cc.cc_dir / 'CyberChef_v11.4.0.html').exists()


def test_concurrent_install_is_refused(cc):
    lock = cc.admin_module._cyberchef_install_lock
    assert lock.acquire(blocking=False)
    try:
        assert _post(cc, 'admin', 'install').status_code == 409
    finally:
        lock.release()


def test_check_update_reports_the_pin_without_network(cc):
    resp = cc.client_for('admin').get('/api/admin/cyberchef/check-update')
    assert resp.status_code == 200
    assert resp.get_json()['latest_version'] == cc.admin_module.CYBERCHEF_VERSION
    assert cc.requested == []


# ------------------------------------------------------------------ serving

def test_cyberchef_page_is_sandboxed_and_assets_are_public(cc):
    assert _post(cc, 'admin', 'install').status_code == 200
    page = cc.client_for('viewer').get('/api/admin/cyberchef/')
    assert page.status_code == 200
    csp = page.headers['Content-Security-Policy']
    assert 'sandbox allow-scripts' in csp and 'allow-same-origin' not in csp

    # The sandboxed page has an opaque origin, so its asset requests carry no session.
    anon = cc.app.test_client()
    asset = anon.get('/api/admin/cyberchef/assets/main.js')
    assert asset.status_code == 200 and asset.headers.get('Access-Control-Allow-Origin') == '*'
    assert 'sandbox' in asset.headers['Content-Security-Policy']
    assert anon.get('/api/admin/cyberchef/').status_code == 401          # the page still needs a login


def test_cyberchef_paths_cannot_leave_the_install_folder(cc):
    anon = cc.app.test_client()
    for path in ('../version.json', '..%2F..%2Fsecret', '/etc/hosts'):
        assert anon.get(f'/api/admin/cyberchef/{path}', follow_redirects=True).status_code in (401, 404)

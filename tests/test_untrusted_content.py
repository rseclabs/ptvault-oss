"""M-4: uploaded files and exported report HTML never run on the app origin.

/api/evidence/<id>/file serves only raster images inline; anything else
(.html, .txt, .pdf, ...) is an attachment. Every evidence file response and
every exported report HTML response carries a sandbox CSP, so even when a
browser renders it, it gets a unique origin and no script. The print
fallback renders the report HTML in a sandboxed iframe instead of
document.write()-ing it into a same-origin popup.
"""

import pathlib
import re

import pytest
from flask import Flask, Response

from config import Config
from tests.conftest import ENGAGEMENT_A
from tests.test_browser_xss import AUDIT, browser, ui  # noqa: F401  (fixtures)
from utils.security_headers import SANDBOX_CSP, apply_security_headers

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = b'<html><body><script>alert(document.domain)</script></body></html>'
PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
                    '1f15c4890000000d49444154789c636000010000050001a5f645400000000049454e44ae426082')


@pytest.fixture
def files(live_app):
    folder = pathlib.Path(Config.UPLOAD_FOLDER) / str(ENGAGEMENT_A)
    folder.mkdir(parents=True)
    conn = live_app.db()
    ids = {}
    for name, body in (('page.html', HTML), ('shot.png', PNG), ('photo.JPG', PNG), ('notes.txt', HTML),
                       ('doc.pdf', b'%PDF-1.4'), ('scan.xml', b'<x/>')):
        (folder / name).write_bytes(body)
        ids[name] = conn.execute(
            "INSERT INTO evidence (engagement_id, evidence_type, title, file_path, file_name) "
            "VALUES (?, 'screenshot', ?, ?, ?)", (ENGAGEMENT_A, name, f'{ENGAGEMENT_A}/{name}', name)).lastrowid
    conn.commit()
    conn.close()
    live_app.ids = ids
    return live_app


def _get(live, name, route):
    return live.client_for('viewer', active_engagement=ENGAGEMENT_A).get(f'/api/evidence/{live.ids[name]}/{route}')


def _sandboxed(resp):
    csp = resp.headers.get('Content-Security-Policy', '')
    return 'sandbox' in csp and "default-src 'none'" in csp and resp.headers.get('X-Content-Type-Options') == 'nosniff'


@pytest.mark.parametrize('name', ['page.html', 'notes.txt', 'doc.pdf', 'scan.xml'])
def test_inline_route_serves_non_images_as_attachments(files, name):
    resp = _get(files, name, 'file')
    assert resp.status_code == 200
    assert resp.headers.get('Content-Disposition', '').startswith('attachment')
    assert _sandboxed(resp)
    assert not resp.mimetype.startswith('text/html')


@pytest.mark.parametrize('name, mimetype', [('shot.png', 'image/png'), ('photo.JPG', 'image/jpeg')])
def test_inline_route_still_serves_images_inline(files, name, mimetype):
    resp = _get(files, name, 'file')
    assert resp.status_code == 200 and resp.mimetype == mimetype
    assert not resp.headers.get('Content-Disposition', '').startswith('attachment')
    assert _sandboxed(resp)


@pytest.mark.parametrize('name', ['page.html', 'shot.png'])
def test_download_route_is_a_sandboxed_attachment(files, name):
    resp = _get(files, name, 'download')
    assert resp.status_code == 200
    assert resp.headers.get('Content-Disposition', '').startswith('attachment')
    assert _sandboxed(resp)


# ------------------------------------------------------------------ report exports

@pytest.fixture
def report(live_app):
    conn = live_app.db()
    report_id = conn.execute("INSERT INTO reports (engagement_id, name, structure) VALUES (?, 'R', '[]')",
                             (ENGAGEMENT_A,)).lastrowid
    conn.commit()
    conn.close()
    live_app.report_id = report_id
    return live_app


def test_html_export_is_sandboxed(report):
    resp = report.client_for('viewer', active_engagement=ENGAGEMENT_A).get(
        f'/api/reporting/reports/{report.report_id}/export?format=html')
    assert resp.status_code == 200 and _sandboxed(resp)


def test_pdf_print_fallback_is_sandboxed(report, monkeypatch):
    import routes.reporting
    monkeypatch.setattr(routes.reporting, 'HAS_WEASYPRINT', False)
    resp = report.client_for('viewer', active_engagement=ENGAGEMENT_A).get(
        f'/api/reporting/reports/{report.report_id}/export?format=pdf')
    assert resp.status_code == 200 and resp.mimetype == 'text/html' and _sandboxed(resp)


# ------------------------------------------------------------------ app-wide header hook

def _hooked_app():
    app = Flask(__name__)
    app.after_request(apply_security_headers)

    @app.route('/plain')
    def plain():
        return 'ok'

    @app.route('/own-csp')
    def own_csp():
        return Response('x', headers={'Content-Security-Policy': SANDBOX_CSP})

    return app.test_client()


def test_header_hook_keeps_a_route_sandbox():
    client = _hooked_app()
    assert client.get('/own-csp').headers['Content-Security-Policy'] == SANDBOX_CSP
    default = client.get('/plain').headers['Content-Security-Policy']
    assert "default-src 'self'" in default and 'sandbox' not in default


def test_app_uses_the_shared_header_hook():
    source = (ROOT / 'app.py').read_text()
    assert 'apply_security_headers' in source
    assert "response.headers['Content-Security-Policy'] = csp" not in source


# ------------------------------------------------------------------ print fallback (client)

def test_no_document_write_in_client_code():
    hits = [f'{p.relative_to(ROOT)}:{s.count(chr(10), 0, m.start()) + 1}'
            for p in (ROOT / 'static/js').rglob('*.js') for s in [p.read_text()]
            for m in re.finditer(r'document\.write(ln)?\s*\(', s)]
    assert not hits, hits


def test_print_fallback_runs_no_report_script(ui):
    result = ui.page.evaluate("""async () => {
        const opened = [];
        const savedOpen = window.open;
        window.open = (...args) => { opened.push(args); return null; };
        try {
            ReportingManager._printHtml('<html><body><p id="r">report</p>'
                + '<script>parent.__xss.push("script")<\\/script>'
                + '<img src=x onerror="parent.__xss.push(\\'img\\')"></body></html>');
            await new Promise(r => setTimeout(r, 400));
        } finally {
            window.open = savedOpen;
        }
        const frame = document.querySelector('iframe[data-print-frame]');
        return { opened: opened.length, sandbox: frame && frame.getAttribute('sandbox'),
                 rendered: !!(frame && frame.contentDocument && frame.contentDocument.getElementById('r')) };
    }""")
    assert result['opened'] == 0
    assert result['sandbox'] is not None and 'allow-scripts' not in result['sandbox']
    assert result['rendered']
    assert ui.page.evaluate(AUDIT)['fired'] == []

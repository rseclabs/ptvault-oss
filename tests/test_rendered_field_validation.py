"""H-10 (server side): fields the UI renders are validated where they are stored.

Ports must be integers and protocol/state come from a fixed list, host colours
from the palette, saved report items carry only safe ids and allow-listed
structural values, and the Markdown sanitizer drops script-capable links.
"""

import io
import json

import pytest

from routes.reporting import _sanitize_html, hydrate_report_item
from tests.conftest import ENGAGEMENT_A

INJECT = '"><img src=x onerror=alert(1)>'


@pytest.fixture
def host(live_app):
    conn = live_app.db()
    host_id = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.0.0.1')", (ENGAGEMENT_A,)).lastrowid
    port_id = conn.execute("INSERT INTO host_ports (host_id, port, protocol, state) VALUES (?, 22, 'tcp', 'open')",
                           (host_id,)).lastrowid
    conn.commit()
    conn.close()
    live_app.host_id, live_app.port_id = host_id, port_id
    return live_app


def _editor(live):
    return live.client_for('editor', active_engagement=ENGAGEMENT_A)


# ------------------------------------------------------------------ ports

@pytest.mark.parametrize('body', [
    {'port': INJECT},
    {'port': '80 onmouseover=alert(1)'},
    {'port': 70000},
    {'port': -1},
    {'port': True},
    {'port': 80, 'protocol': INJECT},
    {'port': 80, 'state': INJECT},
])
def test_create_port_rejects_invalid_fields(host, body):
    resp = _editor(host).post(f'/api/hosts/{host.host_id}/ports', json=body)
    assert resp.status_code == 400, resp.get_json()


def test_create_port_stores_an_integer(host):
    resp = _editor(host).post(f'/api/hosts/{host.host_id}/ports',
                              json={'port': '8080', 'protocol': 'UDP', 'state': 'open|filtered'})
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body['port'] == 8080 and body['protocol'] == 'udp' and body['state'] == 'open|filtered'


def test_update_port_rejects_invalid_state(host):
    resp = _editor(host).put(f'/api/hosts/{host.host_id}/ports/{host.port_id}', json={'state': INJECT})
    assert resp.status_code == 400
    resp = _editor(host).put(f'/api/hosts/{host.host_id}/ports/{host.port_id}', json={'state': 'closed'})
    assert resp.status_code == 200 and resp.get_json()['state'] == 'closed'


def test_engagement_import_skips_invalid_ports(host):
    export = {
        'export_metadata': {'version': '1.0'},
        'engagement': {'name': 'Restored'},
        'hosts': [{'id': 7, 'ip': '10.9.9.9'}],
        'host_ports': [
            {'host_id': 7, 'port': INJECT, 'protocol': 'tcp', 'state': 'open'},
            {'host_id': 7, 'port': 443, 'protocol': INJECT, 'state': 'open'},
            {'host_id': 7, 'port': 444, 'protocol': 'tcp', 'state': INJECT},
            {'host_id': 7, 'port': 80, 'protocol': 'tcp', 'state': 'open'},
        ],
    }
    client = host.client_for('editor', active_engagement=ENGAGEMENT_A)
    resp = client.post('/api/engagements/import', data={
        'file': (io.BytesIO(json.dumps(export).encode()), 'export.json')}, content_type='multipart/form-data')
    assert resp.status_code in (200, 201), resp.get_json()
    conn = host.db()
    rows = conn.execute("SELECT p.port, p.protocol, p.state FROM host_ports p JOIN hosts h ON h.id = p.host_id "
                        "WHERE h.ip = '10.9.9.9'").fetchall()
    conn.close()
    assert [tuple(r) for r in rows] == [(80, 'tcp', 'open')]


# ------------------------------------------------------------------ host colour

@pytest.mark.parametrize('colour', [INJECT, 'red" onclick="x', 'javascript'])
def test_host_colour_must_be_from_the_palette(host, colour):
    resp = _editor(host).put(f'/api/hosts/{host.host_id}', json={'color_category': colour})
    assert resp.status_code == 400


@pytest.mark.parametrize('colour', ['red', 'teal', None, ''])
def test_host_colour_accepts_palette_values_and_clearing(host, colour):
    resp = _editor(host).put(f'/api/hosts/{host.host_id}', json={'color_category': colour})
    assert resp.status_code == 200, resp.get_json()


# ------------------------------------------------------------------ saved report items

def test_hydrated_format_tool_has_safe_id_and_known_tool(live_app):
    conn = live_app.db()
    item = hydrate_report_item(conn.cursor(), {
        'id': "x');alert(1);//", 'type': 'format_tool', 'format_tool_id': "spacer');alert(1);//",
        'title': 't'}, ENGAGEMENT_A)
    conn.close()
    assert item['id'] and all(c.isalnum() or c in '-_' for c in item['id'])
    assert item['format_tool_id'] is None


def test_hydrated_writeup_has_allow_listed_structure(live_app):
    conn = live_app.db()
    writeup_id = conn.execute("INSERT INTO writeups (name, criticality, writeup_type) VALUES ('w', 'high', 'finding')"
                              ).lastrowid
    conn.commit()
    item = hydrate_report_item(conn.cursor(), {
        'id': 'abc-123', 'type': 'writeup', 'source_id': writeup_id,
        'customizations': {'criticality': INJECT, 'heading_level': 'h3><img src=x onerror=alert(1)>'}},
        ENGAGEMENT_A)
    conn.close()
    assert item['id'] == 'abc-123'
    assert item['criticality'] == 'medium'
    assert item['heading_level'] == 'h3'


# ------------------------------------------------------------------ Markdown sanitizer links

@pytest.mark.parametrize('href', [
    'javascript:alert(1)', ' JavaScript:alert(1)', 'java\tscript:alert(1)', '&#106;avascript:alert(1)',
    'data:text/html,<script>alert(1)</script>', 'vbscript:msgbox(1)',
])
def test_sanitizer_drops_script_links(href):
    out = _sanitize_html(f'<a href="{href}">x</a>')
    assert 'script:' not in out.lower().replace('&#106;', 'j') and 'data:' not in out


@pytest.mark.parametrize('href', ['https://example.com/a?b=1', 'http://x', 'mailto:a@b.c', '#sec', '/rel/path'])
def test_sanitizer_keeps_safe_links(href):
    assert f'href="{href}"' in _sanitize_html(f'<a href="{href}">x</a>')

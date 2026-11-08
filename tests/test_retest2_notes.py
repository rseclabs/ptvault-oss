"""Non-security 500s and loose ends from the second retest's notes.

Bulk export with an out-of-scope ID, FTS syntax errors in search, an unknown
attack-map node type, a report template whose structure is not a list, and an
evidence row left without its file when storing the file fails.
"""

import io

import pytest

from models import upload_store
from tests.conftest import ENGAGEMENT_A


def _editor(live):
    return live.client_for('editor', active_engagement=ENGAGEMENT_A)


def test_bulk_export_skips_ids_outside_the_engagement(live_app):
    client = _editor(live_app)
    ev = client.post('/api/evidence', json={'evidence_type': 'note', 'title': 't'}).get_json()
    resp = client.post('/api/evidence/bulk', json={'operation': 'export', 'evidence_ids': [ev['id'], 999999]})
    assert resp.status_code == 200, resp.get_json()
    assert f'"id":{ev["id"]}' in resp.get_data(as_text=True).replace(' ', '')


@pytest.mark.parametrize('q', ['"', 'a OR', 'NEAR(', 'title:', '*'])
def test_search_syntax_errors_are_not_a_500(live_app, q):
    resp = _editor(live_app).get('/api/evidence/search', query_string={'q': q})
    assert resp.status_code in (200, 400), resp.status_code


def test_unknown_attack_map_node_type_is_a_400(live_app):
    client = _editor(live_app)
    m = client.post('/api/attack-maps', json={'name': 'm'}).get_json()
    assert client.post(f"/api/attack-maps/{m['id']}/nodes", json={'node_type': 'host'}).status_code == 400
    assert client.post(f"/api/attack-maps/{m['id']}/nodes", json={'node_type': 'tactic'}).status_code == 201


@pytest.mark.parametrize('structure', ['"text"', '{"a": 1}', '[1, "x", null]', '5'])
def test_template_structure_that_is_not_a_list_of_sections_renders_nothing(structure):
    from utils.template_renderer import TemplateRenderer
    renderer = TemplateRenderer.__new__(TemplateRenderer)
    assert isinstance(renderer.render_template(structure), list)


def test_evidence_is_not_kept_without_its_file(live_app, monkeypatch):
    def broken(*args):
        raise OSError('disk full')
    monkeypatch.setattr(upload_store, 'write_file', broken)
    client = _editor(live_app)
    resp = client.post('/api/evidence', data={'evidence_type': 'other', 'title': 'orphan-check',
                                              'file': (io.BytesIO(b'x'), 'a.txt')}, content_type='multipart/form-data')
    assert resp.status_code == 500
    conn = live_app.db()
    left = conn.execute("SELECT COUNT(*) FROM evidence WHERE title = 'orphan-check'").fetchone()[0]
    conn.close()
    assert left == 0

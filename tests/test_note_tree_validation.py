"""Note-tree ordering fields are integers (retest H-15).

H-15: sort_order (and parent_id) were stored as sent, so a string such as
'"><img onerror=...>' landed in the database and the tree wrote it into a
data- attribute unescaped. Both the host and engagement note trees accept
only an integer or null for these fields, on create and on move.
"""

import pytest

from models.dao.note_tree_dao import NoteTreeDAO
from tests.conftest import ENGAGEMENT_A

INJECT = '"><img src=x onerror=alert(1)>'
BAD = [INJECT, '3', 1.5, True, [], {}]


@pytest.fixture
def tree(live_app):
    conn = live_app.db()
    host_id = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.0.0.1')", (ENGAGEMENT_A,)).lastrowid
    conn.commit()
    conn.close()
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    live_app.bases = {'host': f'/api/hosts/{host_id}/notes', 'engagement': f'/api/engagements/{ENGAGEMENT_A}/notes'}
    live_app.editor = client
    return live_app


def _stored(live, kind):
    table = 'host_notes' if kind == 'host' else 'engagement_notes'
    conn = live.db()
    rows = conn.execute(f'SELECT sort_order, typeof(sort_order) AS t, parent_id FROM {table}').fetchall()
    conn.close()
    return [tuple(r) for r in rows]


@pytest.mark.parametrize('kind', ['host', 'engagement'])
@pytest.mark.parametrize('field', ['sort_order', 'parent_id'])
@pytest.mark.parametrize('value', BAD)
def test_create_rejects_a_non_integer(tree, kind, field, value):
    resp = tree.editor.post(tree.bases[kind], json={'title': 't', field: value})
    assert resp.status_code == 400, resp.get_json()
    assert _stored(tree, kind) == []


@pytest.mark.parametrize('kind', ['host', 'engagement'])
@pytest.mark.parametrize('field', ['sort_order', 'parent_id'])
@pytest.mark.parametrize('value', BAD)
def test_move_rejects_a_non_integer(tree, kind, field, value):
    note = tree.editor.post(tree.bases[kind], json={'title': 't'}).get_json()
    resp = tree.editor.post(f"{tree.bases[kind]}/{note['id']}/move", json={field: value})
    assert resp.status_code == 400, resp.get_json()
    assert _stored(tree, kind) == [(1, 'integer', None)]


@pytest.mark.parametrize('kind', ['host', 'engagement'])
def test_integers_and_null_still_work(tree, kind):
    base = tree.bases[kind]
    parent = tree.editor.post(base, json={'title': 'p', 'sort_order': 5}).get_json()
    assert parent['sort_order'] == 5
    child = tree.editor.post(base, json={'title': 'c', 'parent_id': parent['id'], 'sort_order': None}).get_json()
    assert child['parent_id'] == parent['id']
    moved = tree.editor.post(f"{base}/{child['id']}/move", json={'parent_id': None, 'sort_order': 2})
    assert moved.status_code == 200 and moved.get_json()['sort_order'] == 2
    assert tree.editor.post(f"{base}/{child['id']}/move", json={}).status_code == 200


def test_dao_refuses_non_integers_from_any_caller(app_ctx):
    app_ctx.execute("INSERT INTO engagements (id, name) VALUES (1, 'E')")
    dao = NoteTreeDAO('engagement_notes', 'engagement_id')
    with pytest.raises(ValueError):
        dao.create(1, 'c', sort_order=INJECT)
    with pytest.raises(ValueError):
        dao.create(1, 'c', parent_id='1')
    note_id = dao.create(1, 'c')
    with pytest.raises(ValueError):
        dao.move(note_id, 1, None, INJECT)

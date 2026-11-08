"""The attack-path lookup stays inside the active engagement (retest M-15).

find_path returned _get_path_details([start_id]) when start_id == end_id, and
_get_path_details selected evidence by ID alone, so any user could read the
title, type, tags and linked hosts of another engagement's evidence.
"""

import pytest

from tests.conftest import ENGAGEMENT_A, ENGAGEMENT_B


@pytest.fixture
def evidence(live_app):
    conn = live_app.db()
    ids = {}
    for engagement, title in ((ENGAGEMENT_A, 'A secret evidence'), (ENGAGEMENT_B, 'B evidence')):
        ids[engagement] = conn.execute(
            "INSERT INTO evidence (engagement_id, evidence_type, title, tags) VALUES (?, 'note', ?, 'tag')",
            (engagement, title)).lastrowid
    a2 = conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (?, 'note', 'A second')",
                      (ENGAGEMENT_A,)).lastrowid
    conn.execute("INSERT INTO node_relationships (engagement_id, source_node_type, source_node_id, target_node_type, "
                 "target_node_id, relationship_type) VALUES (?, 'evidence', ?, 'evidence', ?, 'leads_to')",
                 (ENGAGEMENT_A, ids[ENGAGEMENT_A], a2))
    conn.commit()
    conn.close()
    live_app.evidence, live_app.a2 = ids, a2
    return live_app


def test_another_engagements_evidence_is_not_returned(evidence):
    outsider = evidence.client_for('outsider', active_engagement=ENGAGEMENT_B)
    a = evidence.evidence[ENGAGEMENT_A]
    resp = outsider.post('/api/relationships/path', json={'start_id': a, 'end_id': a})
    assert resp.status_code == 200
    assert resp.get_json() == {'path': [], 'length': 0}
    assert 'A secret' not in resp.get_data(as_text=True)


def test_without_an_active_engagement_nothing_is_returned(evidence):
    outsider = evidence.client_for('outsider')
    a = evidence.evidence[ENGAGEMENT_A]
    resp = outsider.post('/api/relationships/path', json={'start_id': a, 'end_id': a})
    assert resp.status_code in (400, 403, 404)
    assert 'A secret' not in resp.get_data(as_text=True)


def test_members_still_get_their_own_path(evidence):
    viewer = evidence.client_for('viewer', active_engagement=ENGAGEMENT_A)
    a = evidence.evidence[ENGAGEMENT_A]
    body = viewer.post('/api/relationships/path', json={'start_id': a, 'end_id': evidence.a2}).get_json()
    assert body['length'] == 2 and [s['evidence']['id'] if 'evidence' in s else s['id'] for s in body['path']] \
        == [a, evidence.a2]


@pytest.mark.parametrize('body', [{'start_id': '1', 'end_id': 1}, {'start_id': [1], 'end_id': 1}, {}, None])
def test_ids_must_be_integers(evidence, body):
    viewer = evidence.client_for('viewer', active_engagement=ENGAGEMENT_A)
    resp = viewer.post('/api/relationships/path', json=body) if body is not None else \
        viewer.post('/api/relationships/path', data='x', content_type='text/plain')
    assert resp.status_code == 400


# ------------------------------------------------------------------ saving a path (retest 2: L-27)

def test_a_saved_path_may_name_only_the_active_engagements_evidence(evidence):
    outsider = evidence.client_for('outsider', active_engagement=ENGAGEMENT_B)
    a, b = evidence.evidence[ENGAGEMENT_A], evidence.evidence[ENGAGEMENT_B]
    for body in ({'start_id': a, 'end_id': b}, {'start_id': b, 'end_id': b, 'path_data': [{'id': a}]},
                 {'start_id': 'x', 'end_id': b}):
        resp = outsider.post('/api/relationships/paths', json={'name': 'p', 'path_data': [{'id': b}], **body})
        assert resp.status_code == 400, body
    ok = outsider.post('/api/relationships/paths', json={'name': 'p', 'start_id': b, 'end_id': b,
                                                          'path_data': [{'id': b}]})
    assert ok.status_code == 201
    conn = evidence.db()
    row = conn.execute('SELECT engagement_id, created_by FROM attack_paths').fetchall()
    conn.close()
    assert [tuple(r) for r in row] == [(ENGAGEMENT_B, evidence.user_ids['outsider'])]

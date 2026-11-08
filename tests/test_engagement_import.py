"""Engagement import (retest L-14).

L-14: the importer becomes the owner of the restored engagement, as on
create; with fail-closed scoping a tester could otherwise not list, activate
or open the engagement they had just imported.
"""

import io
import json

import pytest

from tests.conftest import ENGAGEMENT_A

BASE = {'export_metadata': {'version': '1.0'}, 'engagement': {'name': 'Restored client'}}


def _import(client, payload=BASE):
    return client.post('/api/engagements/import', data={
        'file': (io.BytesIO(json.dumps(payload).encode()), 'export.json')}, content_type='multipart/form-data')


def test_importer_owns_the_restored_engagement(live_app):
    client = live_app.client_for('outsider')                  # a tester with no membership on A
    resp = _import(client)
    assert resp.status_code == 201, resp.get_json()
    new_id = resp.get_json()['engagement_id']

    listed = client.get('/api/engagements').get_json()
    rows = listed['engagements'] if isinstance(listed, dict) else listed
    assert new_id in [e['id'] for e in rows]
    assert client.post('/api/engagements/active', json={'engagement_id': new_id}).status_code == 200

    conn = live_app.db()
    role = conn.execute('SELECT role FROM engagement_members WHERE engagement_id = ? AND user_id = ?',
                        (new_id, live_app.user_ids['outsider'])).fetchone()
    conn.close()
    assert role and role['role'] == 'owner'


def test_import_does_not_grant_access_to_other_engagements(live_app):
    client = live_app.client_for('outsider')
    assert _import(client).status_code == 201
    assert client.post('/api/engagements/active', json={'engagement_id': ENGAGEMENT_A}).status_code in (403, 404)


# ------------------------------------------------------------------ H-17
# Import used to store every value as sent. It now applies the same checks as
# the routes that create each record, and rejects the whole file (nothing is
# written) when one value fails.

INJECT = '<img src=x onerror=alert(1)>'
HOST = {'id': 7, 'ip': '10.0.0.7'}


def _payload(**collections):
    return {**BASE, 'engagement': {**BASE['engagement'], **collections.pop('engagement', {})}, **collections}


def _engagement_count(live):
    conn = live.db()
    count = conn.execute('SELECT COUNT(*) FROM engagements').fetchone()[0]
    conn.close()
    return count


BAD_RECORDS = [
    ('engagement status', {'engagement': {'status': INJECT}}),
    ('engagement start_date', {'engagement': {'start_date': INJECT}}),
    ('engagement end_date', {'engagement': {'end_date': '2026-13-40'}}),
    ('engagement date type', {'engagement': {'start_date': 20260101}}),
    ('engagement email', {'engagement': {'contact_email': INJECT}}),
    ('engagement name type', {'engagement': {'name': {'x': 1}}}),
    ('evidence type', {'evidence': [{'id': 1, 'evidence_type': INJECT, 'title': 't'}]}),
    ('evidence missing type', {'evidence': [{'id': 1, 'title': 't'}]}),
    ('evidence tags', {'evidence': [{'id': 1, 'evidence_type': 'note', 'title': 't', 'tags': 'a,b'}]}),
    ('evidence metadata', {'evidence': [{'id': 1, 'evidence_type': 'note', 'title': 't', 'metadata': [1]}]}),
    ('evidence metadata text', {'evidence': [{'id': 1, 'evidence_type': 'note', 'title': 't', 'metadata': 'nope'}]}),
    ('host credential password_type', {'hosts': [HOST], 'host_credentials': [
        {'host_id': 7, 'username': 'u', 'password_type': INJECT}]}),
    ('engagement credential_type', {'engagement_credentials': [{'username': 'u', 'credential_type': INJECT}]}),
    ('finding criticality', {'engagement_findings': [{'title': 't', 'criticality': INJECT}]}),
    ('finding cvss text', {'engagement_findings': [{'title': 't', 'criticality': 'high', 'cvss_score': INJECT}]}),
    ('finding cvss range', {'engagement_findings': [{'title': 't', 'criticality': 'high', 'cvss_score': 11}]}),
    ('finding missing title', {'engagement_findings': [{'criticality': 'high'}]}),
    ('host indicator', {'hosts': [{**HOST, 'rooted': INJECT}]}),
    ('host ip', {'hosts': [{'id': 7, 'ip': ['10.0.0.7']}]}),
    ('text field type', {'terminal_dumps': [{'title': {'a': 1}, 'content': 'c'}]}),
]


@pytest.mark.parametrize('name, collections', BAD_RECORDS, ids=[n for n, _ in BAD_RECORDS])
def test_import_rejects_values_create_would_reject(live_app, name, collections):
    client = live_app.client_for('outsider')
    before = _engagement_count(live_app)
    resp = _import(client, _payload(**collections))
    assert resp.status_code == 400, resp.get_json()
    assert 'error' in resp.get_json()
    assert _engagement_count(live_app) == before                    # nothing was written


def test_a_complete_valid_export_still_imports(live_app):
    client = live_app.client_for('outsider')
    payload = _payload(
        engagement={'status': 'completed', 'start_date': '2026-01-02', 'end_date': '', 'contact_email': 'a@b.co',
                    'tags': 'x,y'},
        hosts=[{**HOST, 'rooted': 1, 'shell': True}],
        evidence=[{'id': 1, 'evidence_type': 'tool_output', 'title': 't', 'tags': ['a', 'b'],
                   'metadata': {'tool': 'nmap'}},
                  {'id': 2, 'evidence_type': 'note', 'title': 't2', 'metadata': '{"k": 1}'}],
        host_credentials=[{'host_id': 7, 'username': 'u'}, {'host_id': 7, 'username': 'v', 'password_type': 'hash'}],
        engagement_credentials=[{'username': 'u'}, {'username': 'v', 'credential_type': 'ntlm'}],
        engagement_findings=[{'title': 'f'}, {'title': 'g', 'criticality': 'low', 'cvss_score': '7.5'}],
        terminal_dumps=[{'title': 't', 'content': 'c', 'session_datetime': '2026-01-02T03:04'}],
    )
    resp = _import(client, payload)
    assert resp.status_code == 201, resp.get_json()
    new_id = resp.get_json()['engagement_id']

    conn = live_app.db()
    q = lambda sql: [tuple(r) for r in conn.execute(sql, (new_id,)).fetchall()]
    assert q('SELECT status, start_date, end_date FROM engagements WHERE id = ?') == [('completed', '2026-01-02', None)]
    assert q('SELECT rooted, shell FROM hosts WHERE engagement_id = ?') == [(1, 1)]
    assert q('SELECT password_type FROM host_credentials hc JOIN hosts h ON h.id = hc.host_id '
             'WHERE h.engagement_id = ? ORDER BY hc.id') == [('cleartext',), ('hash',)]
    assert q('SELECT credential_type FROM engagement_credentials WHERE engagement_id = ? ORDER BY id') == \
        [('clear_text',), ('ntlm',)]
    assert q('SELECT criticality, cvss_score FROM engagement_findings WHERE engagement_id = ? ORDER BY id') == \
        [('medium', None), ('low', 7.5)]
    assert q('SELECT metadata FROM evidence WHERE engagement_id = ? ORDER BY id') == \
        [('{"tool": "nmap"}',), ('{"k": 1}',)]
    conn.close()


def test_an_export_from_the_app_imports_again(live_app):
    """The checks accept everything the app itself exports."""
    owner = live_app.client_for('owner', active_engagement=ENGAGEMENT_A)
    host = owner.post('/api/hosts', json={'ip': '10.0.0.30', 'hostname': 'dc01'}).get_json()
    owner.post(f"/api/hosts/{host['id']}/credentials", json={'username': 'u', 'password': 'p', 'password_type': 'hash'})
    owner.post(f'/api/engagements/{ENGAGEMENT_A}/credentials', json={'username': 'u', 'credential_type': 'ntlm'})
    owner.post(f'/api/engagements/{ENGAGEMENT_A}/findings', json={'title': 'f', 'criticality': 'high', 'cvss_score': 8.1})
    owner.post(f'/api/engagements/{ENGAGEMENT_A}/terminal-dumps', json={'title': 't', 'content': 'c'})
    owner.post('/api/evidence', json={'evidence_type': 'note', 'title': 'n', 'content': 'c', 'tags': 'a,b'})
    owner.put(f'/api/engagements/{ENGAGEMENT_A}', json={'status': 'completed', 'start_date': '2026-01-01'})

    export = owner.get(f'/api/engagements/{ENGAGEMENT_A}/export/json')
    assert export.status_code == 200
    data = export.get_json()
    assert data['engagement_findings'] and data['host_credentials'] and data['evidence']
    resp = _import(owner, data)
    assert resp.status_code == 201, resp.get_json()

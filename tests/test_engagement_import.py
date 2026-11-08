"""Engagement import (retest L-14).

L-14: the importer becomes the owner of the restored engagement, as on
create; with fail-closed scoping a tester could otherwise not list, activate
or open the engagement they had just imported.
"""

import io
import json

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

"""H-11: evidence file operations stay inside the engagement's upload folder.

A stored file_path that is absolute, climbs out with '..', or points into
another engagement's folder is never deleted, parsed or served. Imported
evidence does not keep a file_path at all, since an export carries no files.
"""

import io
import json
import os

import pytest

from config import Config
from tests.conftest import ENGAGEMENT_A, ENGAGEMENT_B


@pytest.fixture
def files(live_app, tmp_path):
    upload = tmp_path / 'uploads'
    (upload / str(ENGAGEMENT_A)).mkdir(parents=True)
    (upload / str(ENGAGEMENT_B)).mkdir(parents=True)
    assert Config.UPLOAD_FOLDER == str(upload)

    outside = tmp_path / 'ptvault.db'
    outside.write_text('database stand-in')
    other_engagement = upload / str(ENGAGEMENT_B) / 'b-only.xml'
    other_engagement.write_text('<b/>')
    own = upload / str(ENGAGEMENT_A) / '1_own.txt'
    own.write_text('own evidence')

    paths = {
        'dotdot': '../ptvault.db',
        'absolute': str(outside),
        'other_engagement': f'{ENGAGEMENT_B}/b-only.xml',
        'own': f'{ENGAGEMENT_A}/1_own.txt',
    }
    conn = live_app.db()
    ids = {}
    for name, path in paths.items():
        ids[name] = conn.execute(
            "INSERT INTO evidence (engagement_id, evidence_type, title, file_path, file_name) "
            "VALUES (?, 'tool_output', ?, ?, 'f.xml')", (ENGAGEMENT_A, name, path)).lastrowid
    conn.commit()
    conn.close()
    live_app.ids, live_app.outside, live_app.other, live_app.own = ids, outside, other_engagement, own
    return live_app


def _editor(live):
    return live.client_for('editor', active_engagement=ENGAGEMENT_A)


@pytest.mark.parametrize('name', ['dotdot', 'absolute', 'other_engagement'])
def test_delete_never_removes_files_outside_the_engagement(files, name):
    resp = _editor(files).delete(f"/api/evidence/{files.ids[name]}")
    assert resp.status_code == 204          # the record itself is deleted
    assert files.outside.exists() and files.other.exists()


def test_bulk_delete_never_removes_files_outside_the_engagement(files):
    ids = [files.ids[n] for n in ('dotdot', 'absolute', 'other_engagement')]
    resp = _editor(files).post('/api/evidence/bulk', json={'operation': 'delete', 'evidence_ids': ids})
    assert resp.status_code == 200
    assert files.outside.exists() and files.other.exists()


def test_delete_still_removes_the_engagements_own_file(files):
    assert _editor(files).delete(f"/api/evidence/{files.ids['own']}").status_code == 204
    assert not files.own.exists()


@pytest.mark.parametrize('name', ['dotdot', 'absolute', 'other_engagement'])
def test_parse_refuses_paths_outside_the_engagement(files, name):
    resp = _editor(files).post(f"/api/evidence/{files.ids[name]}/parse")
    assert resp.status_code in (403, 404)


@pytest.mark.parametrize('name', ['dotdot', 'absolute', 'other_engagement'])
def test_download_and_view_refuse_paths_outside_the_engagement(files, name):
    client = _editor(files)
    for suffix in ('download', 'file'):
        resp = client.get(f"/api/evidence/{files.ids[name]}/{suffix}")
        assert resp.status_code in (403, 404), suffix
        assert b'database stand-in' not in resp.data and b'<b/>' not in resp.data


def test_imported_evidence_keeps_no_file_reference(files):
    export = {
        'export_metadata': {'version': '1.0'},
        'engagement': {'name': 'Restored'},
        'evidence': [{'id': 1, 'evidence_type': 'note', 'title': 'planted',
                      'file_path': '../ptvault.db', 'file_name': 'x.db', 'file_size': 10}],
    }
    client = files.client_for('editor', active_engagement=ENGAGEMENT_A)
    resp = client.post('/api/engagements/import', data={
        'file': (io.BytesIO(json.dumps(export).encode()), 'export.json')}, content_type='multipart/form-data')
    assert resp.status_code in (200, 201), resp.get_json()

    conn = files.db()
    row = conn.execute("SELECT engagement_id, id, file_path, file_name FROM evidence WHERE title = 'planted'").fetchone()
    conn.close()
    assert row['file_path'] is None and row['file_name'] is None

    # Deleting the restored evidence cannot reach the planted path either.
    restored = files.client_for('admin', active_engagement=row['engagement_id'])
    assert restored.delete(f"/api/evidence/{row['id']}").status_code == 204
    assert files.outside.exists()

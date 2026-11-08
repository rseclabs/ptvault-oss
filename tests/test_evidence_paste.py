# tests/test_evidence_paste.py
"""Tests for the clipboard-paste evidence flow.

Covers:
- GET /api/evidence/<id>/file serves inline (no Content-Disposition: attachment).
- POST /api/evidence honors metadata.host_id by creating an evidence_hosts link.
- /file route 401/403/404 isolation cases.
"""

import io
import json
import os
import sys
from functools import wraps

import pytest
from flask import Flask, g, session


# Ensure project root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _make_passthrough_auth(test_db, user_id=1, role='admin', engagement_id=1):
    """Stub `require_auth` to set g.db/g.current_user/g.active_engagement_id."""
    def _stub_require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            g.db = test_db
            g.current_user = user_id
            g.current_user_role = role
            g.current_username = 'tester'
            session['active_engagement_id'] = engagement_id
            g.active_engagement_id = engagement_id
            return f(*args, **kwargs)
        return wrapper
    return _stub_require_auth


def _make_passthrough_engagement():
    """Stub `require_active_engagement` to pass through."""
    def _stub_require_active_engagement(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapper
    return _stub_require_active_engagement


@pytest.fixture
def evidence_app(test_db, monkeypatch, tmp_path):
    """Flask app with evidence_bp mounted, auth + engagement shimmed, upload dir tmp."""
    import importlib
    import middleware.auth as auth_module
    import routes.engagements as engagements_module
    from config import Config

    monkeypatch.setattr(auth_module, 'require_auth', _make_passthrough_auth(test_db))
    monkeypatch.setattr(
        engagements_module,
        'require_active_engagement',
        _make_passthrough_engagement(),
    )
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path))
    # The database is the in-memory test_db; keep the encryption state checks
    # (models.upload_store, M-14) away from the real data/ folder too.
    monkeypatch.setattr(Config, 'DATABASE_PATH', str(tmp_path / 'unused.db'))
    monkeypatch.setattr(Config, 'ENCRYPTION_KEY_FILE', str(tmp_path / 'unused.key'))
    monkeypatch.setattr(Config, 'ENCRYPTION_SALT_FILE', str(tmp_path / 'unused.salt'))

    import routes.evidence as evidence_module
    importlib.reload(evidence_module)

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.register_blueprint(evidence_module.evidence_bp)

    # Seed minimal engagement row so foreign keys hold
    cur = test_db.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Test Engagement')")
    test_db.commit()

    return app, tmp_path


def _insert_evidence_with_file(test_db, upload_root, engagement_id=1,
                               filename='shot.png', body=b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00'):
    """Insert an evidence row whose file_path points at an on-disk PNG."""
    eng_dir = os.path.join(str(upload_root), str(engagement_id))
    os.makedirs(eng_dir, exist_ok=True)
    full_path = os.path.join(eng_dir, filename)
    with open(full_path, 'wb') as f:
        f.write(body)

    rel_path = os.path.relpath(full_path, str(upload_root))

    cur = test_db.cursor()
    cur.execute(
        """
        INSERT INTO evidence (engagement_id, evidence_type, title, file_path, file_name, file_size)
        VALUES (?, 'screenshot', 'Test screenshot', ?, ?, ?)
        """,
        (engagement_id, rel_path, filename, len(body)),
    )
    test_db.commit()
    return cur.lastrowid


def test_get_evidence_file_serves_inline(evidence_app, test_db):
    """GET /api/evidence/<id>/file responds with the file body and no attachment disposition."""
    app, upload_root = evidence_app
    evidence_id = _insert_evidence_with_file(test_db, upload_root)

    with app.test_client() as client:
        resp = client.get(f'/api/evidence/{evidence_id}/file')
        assert resp.status_code == 200
        cd = resp.headers.get('Content-Disposition', '')
        assert 'attachment' not in cd, f"unexpected attachment disposition: {cd!r}"
        assert resp.data.startswith(b'\x89PNG'), 'body must be the PNG file we wrote'


def test_post_screenshot_with_host_id_creates_link(evidence_app, test_db):
    """POST /api/evidence with metadata.host_id creates a row in evidence_hosts."""
    app, _ = evidence_app

    # Seed a host so the FK holds
    cur = test_db.cursor()
    cur.execute(
        "INSERT INTO hosts (id, engagement_id, ip) VALUES (88, 1, '10.0.0.1')"
    )
    test_db.commit()

    metadata = json.dumps({'source': 'note_paste', 'host_id': 88})
    data = {
        'evidence_type': 'screenshot',
        'title': 'Pasted screenshot 2026-05-14',
        'metadata': metadata,
    }
    file_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00fake'
    data['file'] = (io.BytesIO(file_bytes), 'pasted.png')

    with app.test_client() as client:
        resp = client.post(
            '/api/evidence',
            data=data,
            content_type='multipart/form-data',
        )
        assert resp.status_code in (200, 201), f"got {resp.status_code}: {resp.data!r}"

    body = json.loads(resp.data)
    evidence_id = body['id']

    cur.execute(
        "SELECT host_id FROM evidence_hosts WHERE evidence_id = ?",
        (evidence_id,),
    )
    linked_hosts = [r[0] for r in cur.fetchall()]
    assert 88 in linked_hosts, f"expected host 88 linked to evidence {evidence_id}; got {linked_hosts}"


def test_post_screenshot_rejects_host_id_from_other_engagement(evidence_app, test_db):
    """POST /api/evidence with metadata.host_id pointing at another engagement's
    host must NOT create an evidence_hosts row. SQLite FK enforcement is off in
    production, so the route validates engagement ownership itself.
    """
    app, _ = evidence_app

    # Seed a second engagement + a host inside it. The active engagement is 1
    # (from the evidence_app fixture); this host belongs to engagement 2.
    cur = test_db.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (2, 'Other engagement')")
    cur.execute(
        "INSERT INTO hosts (id, engagement_id, ip) VALUES (77, 2, '192.168.99.99')"
    )
    test_db.commit()

    metadata = json.dumps({'source': 'note_paste', 'host_id': 77})
    file_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00fake'
    data = {
        'evidence_type': 'screenshot',
        'title': 'Pasted screenshot — cross-engagement attempt',
        'metadata': metadata,
        'file': (io.BytesIO(file_bytes), 'pasted.png'),
    }

    with app.test_client() as client:
        resp = client.post(
            '/api/evidence',
            data=data,
            content_type='multipart/form-data',
        )
        # The upload itself succeeds (no fatal error for malicious metadata).
        assert resp.status_code in (200, 201), f"got {resp.status_code}: {resp.data!r}"

    body = json.loads(resp.data)
    evidence_id = body['id']

    # No evidence_hosts row should exist for the cross-engagement host.
    cur.execute(
        "SELECT host_id FROM evidence_hosts WHERE evidence_id = ?",
        (evidence_id,),
    )
    linked_hosts = [r[0] for r in cur.fetchall()]
    assert 77 not in linked_hosts, (
        f"host 77 (in engagement 2) was incorrectly linked to evidence {evidence_id} "
        f"created in engagement 1; linked_hosts={linked_hosts}"
    )


def test_get_evidence_file_isolates_engagement(test_db, monkeypatch, tmp_path):
    """GET /file returns 403 when active engagement ≠ evidence engagement."""
    # Wire app with active_engagement_id = 999 (not the evidence's owner)
    import importlib
    import middleware.auth as auth_module
    import routes.engagements as engagements_module
    from config import Config

    monkeypatch.setattr(
        auth_module, 'require_auth',
        _make_passthrough_auth(test_db, engagement_id=999),
    )
    monkeypatch.setattr(
        engagements_module,
        'require_active_engagement',
        _make_passthrough_engagement(),
    )
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path))
    # The database is the in-memory test_db; keep the encryption state checks
    # (models.upload_store, M-14) away from the real data/ folder too.
    monkeypatch.setattr(Config, 'DATABASE_PATH', str(tmp_path / 'unused.db'))
    monkeypatch.setattr(Config, 'ENCRYPTION_KEY_FILE', str(tmp_path / 'unused.key'))
    monkeypatch.setattr(Config, 'ENCRYPTION_SALT_FILE', str(tmp_path / 'unused.salt'))

    import routes.evidence as evidence_module
    importlib.reload(evidence_module)

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.register_blueprint(evidence_module.evidence_bp)

    cur = test_db.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Owned')")
    cur.execute("INSERT INTO engagements (id, name) VALUES (999, 'Other')")
    test_db.commit()

    evidence_id = _insert_evidence_with_file(test_db, tmp_path, engagement_id=1)

    with app.test_client() as client:
        resp = client.get(f'/api/evidence/{evidence_id}/file')
        assert resp.status_code == 403


def test_get_evidence_file_404_when_evidence_missing(evidence_app):
    """GET /file with an unknown evidence id returns 404."""
    app, _ = evidence_app
    with app.test_client() as client:
        resp = client.get('/api/evidence/999999/file')
        assert resp.status_code == 404


def test_get_evidence_file_404_when_file_missing_on_disk(evidence_app, test_db):
    """GET /file returns 404 when DB row exists but the file was removed."""
    app, upload_root = evidence_app
    evidence_id = _insert_evidence_with_file(test_db, upload_root)

    # Remove the file but leave the row
    cur = test_db.cursor()
    cur.execute("SELECT file_path FROM evidence WHERE id = ?", (evidence_id,))
    rel_path = cur.fetchone()[0]
    os.remove(os.path.join(str(upload_root), rel_path))

    with app.test_client() as client:
        resp = client.get(f'/api/evidence/{evidence_id}/file')
        assert resp.status_code == 404

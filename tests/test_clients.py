"""Route-level tests for /api/clients.

Most of the route logic delegates to ClientDAO (covered in
tests/dao/test_client_dao.py). What's tested here is the delete-blocked
409 response shape, which only exists at the route layer.

To exercise routes without setting up a real JWT cookie chain, we
monkeypatch the auth helpers so require_auth waves a synthetic admin
through. The ClientDAO state and DB rows are real.
"""

import json

import pytest
from flask import Flask, g

from models.dao.client_dao import ClientDAO


def _make_passthrough_auth(test_db):
    """Build a require_auth replacement that just stamps g and calls f."""
    from functools import wraps

    def _stub_require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            g.db = test_db
            g.current_user = 1
            g.current_user_role = 'admin'
            g.current_username = 'admin'
            g.active_engagement_id = None
            return f(*args, **kwargs)
        return wrapper
    return _stub_require_auth


@pytest.fixture
def route_app(test_db, monkeypatch):
    """Flask app with clients_bp mounted and auth shimmed for tests.

    routes/clients.py imports `require_auth` from middleware.auth at
    module load time, so we patch the binding on the routes module
    itself and re-import the blueprint after the patch is in place.
    """
    # Force a fresh import so the new (patched) decorator is picked up.
    import importlib
    import middleware.auth as auth_module
    import routes.clients as clients_module

    monkeypatch.setattr(
        auth_module, 'require_auth', _make_passthrough_auth(test_db)
    )
    importlib.reload(clients_module)

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.register_blueprint(clients_module.clients_bp)
    return app


@pytest.fixture
def admin_client(route_app):
    return route_app.test_client()


def test_delete_returns_409_when_engagements_reference_client(
    test_db, route_app, admin_client
):
    cur = test_db.cursor()
    cur.execute(
        "INSERT INTO users (id, username, email, full_name, password_hash, role) "
        "VALUES (1, 'admin', 'admin@x', 'Admin', 'h', 'admin')"
    )
    cur.execute("INSERT INTO clients (name) VALUES ('LinkedCo')")
    cid = cur.lastrowid
    cur.execute(
        "INSERT INTO engagements (name, client_name, client_id) VALUES (?, ?, ?)",
        ('Active Engagement', 'LinkedCo', cid),
    )
    test_db.commit()

    resp = admin_client.delete(f'/api/clients/{cid}')
    assert resp.status_code == 409
    body = json.loads(resp.data)
    assert body['engagement_count'] == 1
    assert 'LinkedCo' in body['error']

    # Client must still exist
    with route_app.app_context():
        g.db = test_db
        assert ClientDAO().find_by_id(cid) is not None


def test_delete_succeeds_when_no_engagements_reference_client(
    test_db, route_app, admin_client
):
    cur = test_db.cursor()
    cur.execute(
        "INSERT INTO users (id, username, email, full_name, password_hash, role) "
        "VALUES (1, 'admin', 'admin@x', 'Admin', 'h', 'admin')"
    )
    cur.execute("INSERT INTO clients (name) VALUES ('FreeCo')")
    cid = cur.lastrowid
    test_db.commit()

    resp = admin_client.delete(f'/api/clients/{cid}')
    assert resp.status_code == 200

    with route_app.app_context():
        g.db = test_db
        assert ClientDAO().find_by_id(cid) is None

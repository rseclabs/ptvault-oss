"""Route-level tests for hierarchical-notes endpoints.

DAO logic is covered in tests/dao/test_note_tree_dao.py. What's tested
here is the route-layer 409 delete-block response shape, which the DAO
doesn't enforce on its own.
"""

import json

import pytest
from flask import Flask, g


def _make_passthrough_auth(test_db):
    from functools import wraps

    def _stub_require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            g.db = test_db
            g.current_user = 1
            g.current_user_role = 'admin'
            g.current_username = 'admin'
            from flask import session
            session['active_engagement_id'] = 1
            g.active_engagement_id = 1
            return f(*args, **kwargs)
        return wrapper
    return _stub_require_auth


@pytest.fixture
def route_app(test_db, monkeypatch):
    """Flask app with engagements_bp mounted, auth shimmed."""
    import importlib
    import middleware.auth as auth_module
    import routes.engagements as engagements_module

    monkeypatch.setattr(
        auth_module, 'require_auth', _make_passthrough_auth(test_db)
    )
    importlib.reload(engagements_module)

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.register_blueprint(engagements_module.engagements_bp)
    return app


def test_delete_engagement_note_blocked_when_children_exist(test_db, route_app):
    cur = test_db.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Test')")
    cur.execute(
        "INSERT INTO engagement_notes (id, engagement_id, content, parent_id, sort_order) "
        "VALUES (10, 1, 'parent', NULL, 1)"
    )
    cur.execute(
        "INSERT INTO engagement_notes (id, engagement_id, content, parent_id, sort_order) "
        "VALUES (11, 1, 'child', 10, 1)"
    )
    test_db.commit()

    with route_app.test_client() as client:
        resp = client.delete('/api/engagements/1/notes/10')
        assert resp.status_code == 409
        body = json.loads(resp.data)
        assert body['child_count'] == 1
        assert 'child note' in body['error']

        # Parent must still exist
        cur.execute("SELECT 1 FROM engagement_notes WHERE id = 10")
        assert cur.fetchone() is not None


def test_delete_engagement_note_succeeds_for_leaf(test_db, route_app):
    cur = test_db.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Test')")
    cur.execute(
        "INSERT INTO engagement_notes (id, engagement_id, content, parent_id, sort_order) "
        "VALUES (20, 1, 'leaf', NULL, 1)"
    )
    test_db.commit()

    with route_app.test_client() as client:
        resp = client.delete('/api/engagements/1/notes/20')
        assert resp.status_code == 204
        cur.execute("SELECT 1 FROM engagement_notes WHERE id = 20")
        assert cur.fetchone() is None


def test_move_engagement_note_rejects_cycle(test_db, route_app):
    cur = test_db.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Test')")
    cur.execute(
        "INSERT INTO engagement_notes (id, engagement_id, content, parent_id, sort_order) "
        "VALUES (30, 1, 'gp', NULL, 1)"
    )
    cur.execute(
        "INSERT INTO engagement_notes (id, engagement_id, content, parent_id, sort_order) "
        "VALUES (31, 1, 'child', 30, 1)"
    )
    test_db.commit()

    with route_app.test_client() as client:
        # Try to make grandparent (30) a child of its descendant (31)
        resp = client.post(
            '/api/engagements/1/notes/30/move',
            json={'parent_id': 31, 'sort_order': None},
        )
        assert resp.status_code == 400
        body = json.loads(resp.data)
        assert 'subtree' in body['error']


def test_create_engagement_note_under_parent(test_db, route_app):
    cur = test_db.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Test')")
    cur.execute(
        "INSERT INTO engagement_notes (id, engagement_id, content, parent_id, sort_order) "
        "VALUES (40, 1, 'parent', NULL, 1)"
    )
    test_db.commit()

    with route_app.test_client() as client:
        resp = client.post(
            '/api/engagements/1/notes',
            json={'content': 'child note', 'parent_id': 40},
        )
        assert resp.status_code == 201
        body = json.loads(resp.data)
        assert body['parent_id'] == 40
        assert body['content'] == 'child note'

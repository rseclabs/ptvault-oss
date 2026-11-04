"""Built-in shell one-liners are a permanent part of the app.

Covers: the seed adds and restores built-ins without touching user one-liners,
migration 031 marks existing built-ins, and the API refuses to change a
built-in or let a non-admin change anything.
"""

import importlib
import inspect
import json

import pytest
from flask import Flask, g

from models.seed_shell_oneliners import BUILTIN_SHELL_ONELINERS, seed_builtin_shell_oneliners
from routes import shell_oneliners as routes

migration_031 = importlib.import_module('models.migrations.versions.031_shell_oneliners_builtin')

TOTAL = len(BUILTIN_SHELL_ONELINERS)


def _count(conn, where='1=1', params=()):
    return conn.execute(f'SELECT COUNT(*) FROM shell_oneliners WHERE {where}', params).fetchone()[0]


def _call(conn, handler, method='GET', body=None, args=(), role='admin', strip_auth=True):
    """Call a route handler in a request context; strip_auth=False keeps the role check."""
    fn = inspect.unwrap(handler) if strip_auth else handler.__wrapped__
    app = Flask(__name__)
    kwargs = {'method': method}
    if body is not None:
        kwargs['data'] = json.dumps(body)
        kwargs['content_type'] = 'application/json'
    with app.test_request_context('/', **kwargs):
        g.db = conn
        g.user_id = 1
        g.current_user_role = role
        resp, status = fn(*args)
        return status, resp.get_json()


@pytest.fixture
def seeded(test_db):
    seed_builtin_shell_oneliners(test_db)
    return test_db


def _builtin_id(conn, index=0):
    item = BUILTIN_SHELL_ONELINERS[index]
    return conn.execute(
        'SELECT id FROM shell_oneliners WHERE is_builtin = 1 AND category = ? AND name = ?',
        (item['category'], item['name'])
    ).fetchone()[0]


# ---------------------------------------------------------------- seed

def test_builtins_cover_all_three_categories():
    categories = {item['category'] for item in BUILTIN_SHELL_ONELINERS}
    assert categories == {'shells', 'reverse_shells', 'shell_upgrades'}
    keys = [(item['category'], item['name']) for item in BUILTIN_SHELL_ONELINERS]
    assert len(keys) == len(set(keys))


def test_seed_adds_every_builtin_once(test_db):
    assert seed_builtin_shell_oneliners(test_db) == (TOTAL, 0)
    assert _count(test_db, 'is_builtin = 1') == TOTAL
    assert seed_builtin_shell_oneliners(test_db) == (0, 0)
    assert _count(test_db) == TOTAL


def test_seed_restores_deleted_and_edited_builtins(seeded):
    deleted, edited = _builtin_id(seeded, 0), _builtin_id(seeded, 1)
    seeded.execute('DELETE FROM shell_oneliners WHERE id = ?', (deleted,))
    seeded.execute("UPDATE shell_oneliners SET command = 'broken' WHERE id = ?", (edited,))
    seeded.commit()

    assert seed_builtin_shell_oneliners(seeded) == (1, 1)
    assert _count(seeded, 'is_builtin = 1') == TOTAL
    command = seeded.execute('SELECT command FROM shell_oneliners WHERE id = ?', (edited,)).fetchone()[0]
    assert command == BUILTIN_SHELL_ONELINERS[1]['command']


def test_seed_leaves_user_oneliners_alone(seeded):
    seeded.execute(
        "INSERT INTO shell_oneliners (category, name, command, is_builtin) "
        "VALUES ('shells', 'My shell', 'sh -i', 0)"
    )
    seeded.commit()
    assert seed_builtin_shell_oneliners(seeded) == (0, 0)
    assert _count(seeded, "name = 'My shell' AND is_builtin = 0") == 1


# ---------------------------------------------------------------- migration 031

def test_migration_marks_unchanged_builtins_and_keeps_edited_ones_as_custom(test_db):
    untouched, edited = BUILTIN_SHELL_ONELINERS[0], BUILTIN_SHELL_ONELINERS[1]
    insert = ('INSERT INTO shell_oneliners (category, subcategory, name, command, description, variables, is_builtin) '
              'VALUES (?, ?, ?, ?, ?, ?, 0)')
    test_db.execute(insert, (untouched['category'], untouched['subcategory'], untouched['name'],
                             untouched['command'], untouched['description'], untouched['variables']))
    test_db.execute(insert, (edited['category'], edited['subcategory'], edited['name'],
                             'my edited command', edited['description'], edited['variables']))
    test_db.commit()

    migration_031.upgrade(test_db)

    assert _count(test_db, 'is_builtin = 1 AND name = ?', (untouched['name'],)) == 1
    assert _count(test_db, 'is_builtin = 0 AND name = ?', (edited['name'],)) == 1

    # The seed then adds only what is missing: everything but the marked row.
    assert seed_builtin_shell_oneliners(test_db) == (TOTAL - 1, 0)
    assert _count(test_db, "command = 'my edited command'") == 1


# ---------------------------------------------------------------- API

def test_update_builtin_is_refused(seeded):
    oid = _builtin_id(seeded)
    status, body = _call(seeded, routes.update_oneliner, 'PUT', {'command': 'x'}, args=(oid,))
    assert status == 403, body
    assert 'Built-in' in body['error']


def test_delete_builtin_is_refused(seeded):
    oid = _builtin_id(seeded)
    status, _ = _call(seeded, routes.delete_oneliner, 'DELETE', args=(oid,))
    assert status == 403
    assert _count(seeded, 'id = ?', (oid,)) == 1


def test_user_oneliner_can_be_created_edited_and_deleted(seeded):
    status, created = _call(seeded, routes.create_oneliner, 'POST', {
        'category': 'reverse_shells', 'name': 'Mine', 'command': 'nc {{LHOST}} {{LPORT}}',
        'variables': [{'name': 'LHOST', 'default': ''}],
    })
    assert status == 201, created
    assert created['is_builtin'] == 0

    status, updated = _call(seeded, routes.update_oneliner, 'PUT', {'command': 'nc -e sh'}, args=(created['id'],))
    assert status == 200, updated
    assert updated['command'] == 'nc -e sh'

    status, _ = _call(seeded, routes.delete_oneliner, 'DELETE', args=(created['id'],))
    assert status == 200
    assert _count(seeded, 'id = ?', (created['id'],)) == 0


def test_list_reports_which_are_builtin(seeded):
    status, items = _call(seeded, routes.list_oneliners)
    assert status == 200
    assert len(items) == TOTAL
    assert all(item['is_builtin'] == 1 for item in items)


@pytest.mark.parametrize('handler, method, body, needs_id', [
    (routes.create_oneliner, 'POST', {'category': 'shells', 'name': 'x', 'command': 'x'}, False),
    (routes.update_oneliner, 'PUT', {'command': 'x'}, True),
    (routes.delete_oneliner, 'DELETE', None, True),
])
@pytest.mark.parametrize('role', ['tester', 'viewer'])
def test_only_admins_can_change_oneliners(seeded, handler, method, body, needs_id, role):
    seeded.execute("INSERT INTO shell_oneliners (category, name, command) VALUES ('shells', 'Mine', 'sh')")
    seeded.commit()
    oid = seeded.execute("SELECT id FROM shell_oneliners WHERE name = 'Mine'").fetchone()[0]
    args = (oid,) if needs_id else ()
    status, _ = _call(seeded, handler, method, body, args=args, role=role, strip_auth=False)
    assert status == 403

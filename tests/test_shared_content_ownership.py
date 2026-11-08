"""M-1: shared content can be changed only by its creator or an admin.

Writeups, custom commands, test-plan templates (and their items) and
ATT&CK layers record created_by. A tester may change only what they created;
rows from before migration 032 have no creator and are admin-only.
"""

import importlib

import pytest

from tests.conftest import ENGAGEMENT_A

migration_032 = importlib.import_module('models.migrations.versions.032_shared_content_owner')
SHARED_TABLES = ('writeups', 'commands', 'test_plans', 'navigator_layers')


def test_migration_adds_created_by(test_db):
    for table in SHARED_TABLES:
        cols = [r[1] for r in test_db.execute(f'PRAGMA table_info({table})')]
        assert 'created_by' in cols, table
    migration_032.upgrade(test_db)  # idempotent


@pytest.fixture
def content(live_app):
    """One row per table created by 'owner' (a tester), and one legacy row with no creator."""
    owner = live_app.user_ids['owner']
    conn = live_app.db()
    ids = {}
    for who, created_by in (('mine', owner), ('legacy', None)):
        ids[f'writeup_{who}'] = conn.execute(
            "INSERT INTO writeups (name, created_by) VALUES (?, ?)", (f'w-{who}', created_by)).lastrowid
        ids[f'command_{who}'] = conn.execute(
            "INSERT INTO commands (category, name, command, is_custom, created_by) VALUES ('c', ?, 'id', 1, ?)",
            (f'cmd-{who}', created_by)).lastrowid
        ids[f'template_{who}'] = conn.execute(
            "INSERT INTO test_plans (name, created_by) VALUES (?, ?)", (f't-{who}', created_by)).lastrowid
        ids[f'layer_{who}'] = conn.execute(
            "INSERT INTO navigator_layers (name, layer_json, created_by) VALUES (?, '{}', ?)",
            (f'l-{who}', created_by)).lastrowid
    conn.commit()
    conn.close()
    live_app.ids = ids
    return live_app


def _requests(ids, which):
    return [
        ('PUT', f"/api/reporting/writeups/{ids['writeup_' + which]}", {'name': 'changed'}),
        ('PUT', f"/api/commands/{ids['command_' + which]}", {'name': 'changed'}),
        ('PUT', f"/api/testplans/plans/{ids['template_' + which]}", {'name': 'changed'}),
        ('POST', f"/api/testplans/plans/{ids['template_' + which]}/items",
         {'technique_id': 'T1059', 'test_name': 'x', 'custom_command': 'id'}),
        ('DELETE', f"/api/testplans/layers/{ids['layer_' + which]}", None),
        ('DELETE', f"/api/commands/{ids['command_' + which]}", None),
        ('DELETE', f"/api/reporting/writeups/{ids['writeup_' + which]}", None),
        ('DELETE', f"/api/testplans/plans/{ids['template_' + which]}", None),
    ]


@pytest.mark.parametrize('user,which,allowed', [
    ('owner', 'mine', True),       # the creator
    ('editor', 'mine', False),     # another tester
    ('admin', 'mine', True),
    ('owner', 'legacy', False),    # no recorded creator: admin only
    ('admin', 'legacy', True),
])
def test_shared_content_edits_need_creator_or_admin(content, user, which, allowed):
    client = content.client_for(user)
    wrong = []
    for method, url, body in _requests(content.ids, which):
        resp = client.open(url, method=method, json=body)
        ok = resp.status_code not in (401, 403)
        if ok != allowed:
            wrong.append((method, url, resp.status_code, resp.get_json(silent=True)))
    assert not wrong


def _created_by(live, table, row_id):
    conn = live.db()
    value = conn.execute(f'SELECT created_by FROM {table} WHERE id = ?', (row_id,)).fetchone()[0]
    conn.close()
    return value


def test_new_content_records_its_creator(live_app):
    client = live_app.client_for('editor')
    me = live_app.user_ids['editor']
    writeup = client.post('/api/reporting/writeups', json={'name': 'new'})
    assert writeup.status_code == 201
    assert _created_by(live_app, 'writeups', writeup.get_json()['id']) == me

    command = client.post('/api/commands', json={'category': 'Recon', 'name': 'n', 'command': 'id'})
    assert command.status_code == 201
    assert _created_by(live_app, 'commands', command.get_json()['id']) == me

    template = client.post('/api/testplans/plans', json={'name': 'T', 'is_template': True})
    assert template.status_code == 201
    assert _created_by(live_app, 'test_plans', template.get_json()['id']) == me


def test_tester_can_create_template_without_active_engagement(live_app):
    # Regression from H-4: template creation needs no engagement.
    resp = live_app.client_for('outsider').post('/api/testplans/plans', json={'name': 'T', 'is_template': True})
    assert resp.status_code == 201


def test_global_viewer_cannot_create_template(live_app):
    resp = live_app.client_for('viewer').post('/api/testplans/plans', json={'name': 'T', 'is_template': True})
    assert resp.status_code == 403


def test_engagement_plan_saved_as_template_belongs_to_the_copier(live_app):
    conn = live_app.db()
    plan = conn.execute("INSERT INTO test_plans (name, engagement_id) VALUES ('A plan', ?)",
                        (ENGAGEMENT_A,)).lastrowid
    conn.commit()
    conn.close()
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    resp = client.post(f'/api/testplans/plans/{plan}/duplicate', json={'target': 'template'})
    assert resp.status_code == 201
    assert _created_by(live_app, 'test_plans', resp.get_json()['id']) == live_app.user_ids['editor']


def test_engagement_plans_still_follow_engagement_roles(live_app):
    conn = live_app.db()
    plan = conn.execute("INSERT INTO test_plans (name, engagement_id) VALUES ('A plan', ?)",
                        (ENGAGEMENT_A,)).lastrowid
    conn.commit()
    conn.close()
    editor = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    assert editor.put(f'/api/testplans/plans/{plan}', json={'name': 'x'}).status_code == 200

"""Regression tests for Test Plans route handlers.

Covers three previously broken paths:
  1. GET /executions (and /executions/<id>) referenced columns that do not
     exist on test_plan_items (tpi.technique_id / tpi.atomic_test_name) and
     always returned 500.
  2. POST /executions/start accepted any host_id, including hosts from other
     engagements or hosts marked out of scope.
  3. GET /atomics pagination: the UI relies on `total`, `limit`, `offset`
     to page through the whole library.

Auth/license decorators need a real session, so the handlers are called
with their decorators stripped via inspect.unwrap, inside a request context
that carries the same `g` values the decorators would set.
"""

import inspect
import json

import pytest
from flask import Flask, g

from routes import testplans as tp_routes


def _call(app_ctx, handler, path='/', method='GET', body=None, query=None,
          args=(), engagement_id=1):
    """Invoke an undecorated route handler and return (status, json)."""
    fn = inspect.unwrap(handler)
    app = Flask(__name__)
    kwargs = {'method': method, 'query_string': query or {}}
    if body is not None:
        kwargs['data'] = json.dumps(body)
        kwargs['content_type'] = 'application/json'
    with app.test_request_context(path, **kwargs):
        g.db = app_ctx
        g.user_id = 1
        g.active_engagement_id = engagement_id
        resp, status = fn(*args)
        return status, resp.get_json()


@pytest.fixture
def plan_data(app_ctx):
    """Engagement 1 + 2, hosts (in/out of scope), atomics, plan, executions."""
    c = app_ctx.cursor()
    c.execute("INSERT INTO engagements (id, name, status) VALUES (1, 'E1', 'active')")
    c.execute("INSERT INTO engagements (id, name, status) VALUES (2, 'E2', 'active')")
    c.execute("INSERT INTO hosts (id, engagement_id, ip, hostname) VALUES (10, 1, '10.0.0.10', 'dc01')")
    c.execute("INSERT INTO hosts (id, engagement_id, ip, out_of_scope) VALUES (11, 1, '10.0.0.11', 1)")
    c.execute("INSERT INTO hosts (id, engagement_id, ip) VALUES (20, 2, '10.9.9.9')")

    tactics = ['discovery', 'execution', 'impact', 'privilege-escalation']
    for i in range(1, 26):
        c.execute(
            "INSERT INTO atomics (id, technique_id, technique_name, tactic, atomic_test_index, "
            "atomic_test_name, supported_platforms, executor_name, executor_command) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, 'powershell', 'whoami')",
            (i, f'T{1000 + i}', f'Technique {i}', tactics[i % len(tactics)],
             f'Test {i}', json.dumps(['windows']))
        )

    c.execute("INSERT INTO test_plans (id, name) VALUES (1, 'Plan A')")
    # One atomic-backed item and one custom item (no atomic_id)
    c.execute("INSERT INTO test_plan_items (id, test_plan_id, atomic_id, sort_order, enabled) VALUES (1, 1, 1, 0, 1)")
    c.execute("INSERT INTO test_plan_items (id, test_plan_id, custom_name, custom_command, sort_order, enabled) "
              "VALUES (2, 1, 'Custom recon', 'id', 1, 1)")
    c.execute("INSERT INTO test_executions (id, engagement_id, test_plan_id, test_plan_item_id, host_id, status) "
              "VALUES (1, 1, 1, 1, 10, 'pending')")
    c.execute("INSERT INTO test_executions (id, engagement_id, test_plan_id, test_plan_item_id, status) "
              "VALUES (2, 1, 1, 2, 'completed')")
    # Execution in another engagement must not leak
    c.execute("INSERT INTO test_executions (id, engagement_id, test_plan_id, test_plan_item_id, status) "
              "VALUES (3, 2, 1, 1, 'pending')")
    app_ctx.commit()
    return app_ctx


# ---------------------------------------------------------------- executions

def test_list_executions_returns_rows_for_active_engagement(plan_data):
    status, body = _call(plan_data, tp_routes.list_executions)
    assert status == 200, body
    assert {e['id'] for e in body} == {1, 2}

    by_id = {e['id']: e for e in body}
    assert by_id[1]['technique_id'] == 'T1001'
    assert by_id[1]['atomic_test_name'] == 'Test 1'
    assert by_id[1]['host_ip'] == '10.0.0.10'
    assert by_id[1]['plan_name'] == 'Plan A'
    # Custom item: name falls back to custom_name, no technique
    assert by_id[2]['technique_id'] is None
    assert by_id[2]['atomic_test_name'] == 'Custom recon'


def test_get_execution_returns_details(plan_data):
    fn = inspect.unwrap(tp_routes.get_execution)
    app = Flask(__name__)
    with app.test_request_context('/'):
        g.db = plan_data
        g.active_engagement_id = 1
        resp, status = fn(1)
    assert status == 200
    data = resp.get_json()
    assert data['technique_id'] == 'T1001'
    assert data['executor_command'] == 'whoami'


def test_get_execution_from_other_engagement_is_404(plan_data):
    fn = inspect.unwrap(tp_routes.get_execution)
    app = Flask(__name__)
    with app.test_request_context('/'):
        g.db = plan_data
        g.active_engagement_id = 1
        resp, status = fn(3)
    assert status == 404


# ----------------------------------------------------------- start execution

def test_start_execution_with_in_scope_host(plan_data):
    status, body = _call(plan_data, tp_routes.start_execution, method='POST',
                         body={'plan_id': 1, 'host_id': 10})
    assert status == 201, body
    assert body['count'] == 2


def test_start_execution_rejects_out_of_scope_host(plan_data):
    status, body = _call(plan_data, tp_routes.start_execution, method='POST',
                         body={'plan_id': 1, 'host_id': 11})
    assert status == 400
    assert 'out of scope' in body['error']


def test_start_execution_rejects_host_from_other_engagement(plan_data):
    status, body = _call(plan_data, tp_routes.start_execution, method='POST',
                         body={'plan_id': 1, 'host_id': 20})
    assert status == 400
    assert 'not found' in body['error']


def test_start_execution_without_host(plan_data):
    status, body = _call(plan_data, tp_routes.start_execution, method='POST',
                         body={'plan_id': 1})
    assert status == 201, body


# ------------------------------------------------------- atomics pagination

def test_list_atomics_paginates_with_total(plan_data):
    status, page1 = _call(plan_data, tp_routes.list_atomics, query={'limit': 10, 'offset': 0})
    assert status == 200
    assert page1['total'] == 25
    assert len(page1['atomics']) == 10

    _, page3 = _call(plan_data, tp_routes.list_atomics, query={'limit': 10, 'offset': 20})
    assert len(page3['atomics']) == 5
    ids = {a['id'] for a in page1['atomics']} & {a['id'] for a in page3['atomics']}
    assert not ids, "pages must not overlap"


def test_list_atomics_total_respects_filters(plan_data):
    status, body = _call(plan_data, tp_routes.list_atomics,
                         query={'tactic': 'impact', 'limit': 2})
    assert status == 200
    assert len(body['atomics']) == 2
    assert body['total'] == sum(1 for i in range(1, 26) if i % 4 == 2)


@pytest.mark.parametrize('limit,expected', [(0, 1), (-5, 1), (5000, 1000)])
def test_list_atomics_clamps_limit(plan_data, limit, expected):
    status, body = _call(plan_data, tp_routes.list_atomics, query={'limit': limit})
    assert status == 200
    assert body['limit'] == expected


def test_list_tactics_covers_whole_library(plan_data):
    status, body = _call(plan_data, tp_routes.list_tactics)
    assert status == 200
    assert {t['tactic'] for t in body} == {
        'discovery', 'execution', 'impact', 'privilege-escalation'}


# ------------------------------------------------- per-engagement plans (026)

def _load_migration_026():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), '..', 'models', 'migrations',
                        'versions', '026_engagement_test_plans.py')
    spec = importlib.util.spec_from_file_location('mig026', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def scoped_plans(plan_data):
    """plan 1 = template (from plan_data); plan 5 in E1; plan 6 in E2."""
    c = plan_data.cursor()
    c.execute("INSERT INTO test_plans (id, name, engagement_id) VALUES (5, 'E1 plan', 1)")
    c.execute("INSERT INTO test_plan_items (id, test_plan_id, atomic_id, sort_order, enabled) VALUES (50, 5, 3, 0, 1)")
    c.execute("INSERT INTO test_plans (id, name, engagement_id) VALUES (6, 'E2 plan', 2)")
    c.execute("INSERT INTO test_plan_items (id, test_plan_id, atomic_id, sort_order, enabled) VALUES (60, 6, 4, 0, 1)")
    plan_data.commit()
    return plan_data


def test_migration_moves_template_executions_into_engagement_copies(plan_data):
    """Legacy data: template plan 1 has executions in E1 and E2."""
    _load_migration_026().upgrade(plan_data)  # idempotent re-run on migrated schema
    c = plan_data.cursor()

    # Template stays a template, untouched
    c.execute("SELECT engagement_id FROM test_plans WHERE id = 1")
    assert c.fetchone()[0] is None
    c.execute("SELECT COUNT(*) FROM test_plan_items WHERE test_plan_id = 1")
    assert c.fetchone()[0] == 2
    c.execute("SELECT COUNT(*) FROM test_executions WHERE test_plan_id = 1")
    assert c.fetchone()[0] == 0, "no executions may remain on the template"

    # Each engagement got its own copy, and its executions point at it
    c.execute("""SELECT te.id, te.engagement_id, tp.engagement_id, tp.source_template_id,
                        tp.name, tpi.test_plan_id = tp.id, tpi.atomic_id, tpi.custom_name
                 FROM test_executions te
                 JOIN test_plans tp ON tp.id = te.test_plan_id
                 JOIN test_plan_items tpi ON tpi.id = te.test_plan_item_id
                 ORDER BY te.id""")
    rows = {r[0]: tuple(r)[1:] for r in c.fetchall()}
    assert rows[1] == (1, 1, 1, 'Plan A', 1, 1, None)
    assert rows[2] == (1, 1, 1, 'Plan A', 1, None, 'Custom recon')
    assert rows[3] == (2, 2, 1, 'Plan A', 1, 1, None)

    c.execute("SELECT COUNT(*) FROM test_plans WHERE source_template_id = 1")
    assert c.fetchone()[0] == 2

    # Deleting the template no longer touches execution history
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("DELETE FROM test_plans WHERE id = 1")
    c.execute("SELECT COUNT(*) FROM test_executions")
    assert c.fetchone()[0] == 3


def test_list_plans_shows_templates_and_active_engagement_only(scoped_plans):
    status, body = _call(scoped_plans, tp_routes.list_plans)
    assert status == 200
    by_id = {p['id']: p for p in body}
    assert set(by_id) == {1, 5}
    assert by_id[1]['is_template'] is True
    assert by_id[5]['is_template'] is False

    _, eng_only = _call(scoped_plans, tp_routes.list_plans, query={'scope': 'engagement'})
    assert [p['id'] for p in eng_only] == [5]
    _, tmpl_only = _call(scoped_plans, tp_routes.list_plans, query={'scope': 'templates'})
    assert [p['id'] for p in tmpl_only] == [1]

    # No active engagement: templates only
    _, none_active = _call(scoped_plans, tp_routes.list_plans, engagement_id=None)
    assert [p['id'] for p in none_active] == [1]


@pytest.mark.parametrize('handler,method,args,body', [
    ('get_plan', 'GET', (6,), None),
    ('update_plan', 'PUT', (6,), {'name': 'x'}),
    ('delete_plan', 'DELETE', (6,), None),
    ('add_bulk_items', 'POST', (6,), {'atomic_ids': [1]}),
    ('delete_plan_item', 'DELETE', (6, 60), None),
    ('reorder_plan_items', 'POST', (6,), {'item_ids': [60]}),
    ('duplicate_plan', 'POST', (6,), {}),
])
def test_other_engagements_plan_is_not_found(scoped_plans, handler, method, args, body):
    status, _ = _call(scoped_plans, getattr(tp_routes, handler), method=method,
                      args=args, body=body)
    assert status == 404
    c = scoped_plans.cursor()
    c.execute("SELECT name FROM test_plans WHERE id = 6")
    assert c.fetchone()[0] == 'E2 plan'
    c.execute("SELECT COUNT(*) FROM test_plan_items WHERE test_plan_id = 6")
    assert c.fetchone()[0] == 1


def test_create_plan_scopes(scoped_plans):
    status, plan = _call(scoped_plans, tp_routes.create_plan, method='POST', body={'name': 'New'})
    assert status == 201
    assert plan['engagement_id'] == 1 and plan['is_template'] is False

    status, tmpl = _call(scoped_plans, tp_routes.create_plan, method='POST',
                         body={'name': 'Tmpl', 'is_template': True})
    assert status == 201
    assert tmpl['engagement_id'] is None and tmpl['is_template'] is True

    status, _ = _call(scoped_plans, tp_routes.create_plan, method='POST',
                      body={'name': 'Orphan'}, engagement_id=None)
    assert status == 400


def test_use_template_copies_into_engagement(scoped_plans):
    status, plan = _call(scoped_plans, tp_routes.duplicate_plan, method='POST',
                         args=(1,), body={'target': 'engagement'})
    assert status == 201
    assert plan['name'] == 'Plan A'
    assert plan['engagement_id'] == 1
    assert plan['source_template_id'] == 1
    assert plan['item_count'] == 2


def test_save_engagement_plan_as_template(scoped_plans):
    status, plan = _call(scoped_plans, tp_routes.duplicate_plan, method='POST',
                         args=(5,), body={'target': 'template'})
    assert status == 201
    assert plan['is_template'] is True
    assert plan['name'] == 'E1 plan (Copy)'
    assert plan['item_count'] == 1


def test_duplicate_defaults_to_same_scope(scoped_plans):
    _, copy = _call(scoped_plans, tp_routes.duplicate_plan, method='POST', args=(5,), body={})
    assert copy['engagement_id'] == 1
    _, tcopy = _call(scoped_plans, tp_routes.duplicate_plan, method='POST', args=(1,), body={})
    assert tcopy['is_template'] is True


def test_start_execution_from_template_runs_an_engagement_copy(scoped_plans):
    c = scoped_plans.cursor()
    c.execute("SELECT COUNT(*) FROM test_executions WHERE test_plan_id = 1")
    before = c.fetchone()[0]

    status, body = _call(scoped_plans, tp_routes.start_execution, method='POST',
                         body={'plan_id': 1})
    assert status == 201
    assert body['copied_from_template'] is True
    new_plan_id = body['plan_id']
    assert new_plan_id != 1

    c.execute("SELECT engagement_id, source_template_id FROM test_plans WHERE id = ?", (new_plan_id,))
    assert tuple(c.fetchone()) == (1, 1)
    c.execute("SELECT COUNT(*) FROM test_executions WHERE test_plan_id = ?", (new_plan_id,))
    assert c.fetchone()[0] == 2
    c.execute("SELECT COUNT(*) FROM test_executions WHERE test_plan_id = 1")
    assert c.fetchone()[0] == before, "template must not gain executions"
    # Execution items belong to the copy, not the template
    c.execute("""SELECT COUNT(*) FROM test_executions te
                 JOIN test_plan_items tpi ON tpi.id = te.test_plan_item_id
                 WHERE te.test_plan_id = ? AND tpi.test_plan_id != ?""", (new_plan_id, new_plan_id))
    assert c.fetchone()[0] == 0


def test_start_execution_engagement_plan_is_not_copied(scoped_plans):
    status, body = _call(scoped_plans, tp_routes.start_execution, method='POST',
                         body={'plan_id': 5})
    assert status == 201
    assert body['plan_id'] == 5 and body['copied_from_template'] is False


def test_start_execution_rejects_other_engagements_plan(scoped_plans):
    status, _ = _call(scoped_plans, tp_routes.start_execution, method='POST',
                      body={'plan_id': 6})
    assert status == 404


# ----------------------------------------------- outcomes and grid (027)

def _update(db, execution_id, body):
    return _call(db, tp_routes.update_execution, method='PUT', args=(execution_id,), body=body)


def test_update_execution_records_outcome_and_detected_by(plan_data):
    status, _ = _update(plan_data, 1, {'outcome': 'alerted', 'detected_by': '  Sysmon -> Splunk  '})
    assert status == 200
    c = plan_data.cursor()
    c.execute("SELECT outcome, detected_by FROM test_executions WHERE id = 1")
    assert tuple(c.fetchone()) == ('alerted', 'Sysmon -> Splunk')

    # Empty string / null clears back to "not evaluated"
    status, _ = _update(plan_data, 1, {'outcome': '', 'detected_by': ''})
    assert status == 200
    c.execute("SELECT outcome, detected_by FROM test_executions WHERE id = 1")
    assert tuple(c.fetchone()) == (None, None)


@pytest.mark.parametrize('body', [{'outcome': 'blocked'}, {'status': 'done'}])
def test_update_execution_rejects_unknown_values(plan_data, body):
    status, resp = _update(plan_data, 1, body)
    assert status == 400
    assert 'must be one of' in resp['error']


def test_update_execution_leaves_outcome_alone_when_omitted(plan_data):
    _update(plan_data, 1, {'outcome': 'prevented'})
    _update(plan_data, 1, {'status': 'completed'})
    c = plan_data.cursor()
    c.execute("SELECT outcome, status FROM test_executions WHERE id = 1")
    assert tuple(c.fetchone()) == ('prevented', 'completed')


def test_list_executions_includes_grid_fields(plan_data):
    c = plan_data.cursor()
    c.execute("INSERT INTO evidence (id, engagement_id, evidence_type, title) VALUES (70, 1, 'note', 'LSASS dump')")
    c.execute("UPDATE test_executions SET evidence_id = 70, outcome = 'logged' WHERE id = 1")
    plan_data.commit()
    _, body = _call(plan_data, tp_routes.list_executions)
    row = next(e for e in body if e['id'] == 1)
    assert row['outcome'] == 'logged'
    assert row['evidence_title'] == 'LSASS dump'
    assert row['item_sort_order'] == 0
    assert row['tactic'] == 'execution'


def test_start_execution_refuses_same_host_twice(scoped_plans):
    status, _ = _call(scoped_plans, tp_routes.start_execution, method='POST',
                      body={'plan_id': 5, 'host_id': 10})
    assert status == 201
    status, body = _call(scoped_plans, tp_routes.start_execution, method='POST',
                         body={'plan_id': 5, 'host_id': 10})
    assert status == 409
    assert 'already been run' in body['error']


def test_start_execution_refuses_no_host_twice(scoped_plans):
    assert _call(scoped_plans, tp_routes.start_execution, method='POST', body={'plan_id': 5})[0] == 201
    assert _call(scoped_plans, tp_routes.start_execution, method='POST', body={'plan_id': 5})[0] == 409


# ------------------------------------------------ session.log import (step 4)

def _import(db, log_text, plan_id, host_id='', apply=False, engagement_id=1):
    import io
    fn = inspect.unwrap(tp_routes.import_session_log)
    app = Flask(__name__)
    data = {
        'file': (io.BytesIO(log_text.encode('utf-8')), 'session.log'),
        'plan_id': str(plan_id),
        'host_id': str(host_id),
        'apply': 'true' if apply else 'false',
    }
    with app.test_request_context('/', method='POST', data=data,
                                  content_type='multipart/form-data'):
        g.db = db
        g.user_id = 1
        g.active_engagement_id = engagement_id
        resp, status = fn()
        return status, resp.get_json()


def _log(*events):
    """events: (n, technique, name, level, tag, output)"""
    lines = []
    for n, technique, name, level, tag, output in events:
        t = f" [item={tag}]" if tag else ''
        lines.append(f"[2026-10-31 10:0{n}:00] [INFO] Preparing test: {technique} - {name}")
        if level == 'SKIP':
            lines.append(f"[2026-10-31 10:0{n}:01] [SKIP] Test {n} skipped by user: {technique}{t}")
            continue
        lines.append(f"[2026-10-31 10:0{n}:01] [START] Executing test {n}: {technique} - {name}{t}")
        lines.append("--- Command Output ----------------------------------------------")
        lines.append(output)
        lines.append("-----------------------------------------------------------------")
        if level in ('PASS', 'FAIL'):
            code = 0 if level == 'PASS' else 2
            word = 'completed successfully' if level == 'PASS' else 'failed'
            lines.append(f"[2026-10-31 10:0{n}:05] [{level}] Test {n} {word} (exit code: {code}, duration: 4s){t}")
    return "\n".join(lines)


def _exec_rows(db, plan_id, host_id):
    c = db.cursor()
    c.execute("""SELECT test_plan_item_id, status, execution_output, execution_started_at,
                        execution_completed_at
                 FROM test_executions WHERE engagement_id = 1 AND test_plan_id = ? AND host_id IS ?
                 ORDER BY test_plan_item_id""", (plan_id, host_id))
    return [tuple(r) for r in c.fetchall()]


def test_import_preview_matches_by_tag_and_writes_nothing(scoped_plans):
    log = _log((1, 'T1003', 'Test 3', 'PASS', 50, 'uid=0(root)'))
    status, body = _import(scoped_plans, log, plan_id=5, host_id=10)
    assert status == 200, body
    assert body['preview'] is True
    assert body['summary'] == {'total': 1, 'matched': 1, 'unmatched': 0, 'new_executions': 1}
    row = body['results'][0]
    assert (row['item_id'], row['matched_by'], row['status']) == (50, 'item', 'completed')
    assert _exec_rows(scoped_plans, 5, 10) == []


def test_import_apply_creates_and_updates_without_duplicating_output(scoped_plans):
    log = _log((1, 'T1003', 'Test 3', 'PASS', 50, 'uid=0(root)'))
    status, body = _import(scoped_plans, log, plan_id=5, host_id=10, apply=True)
    assert status == 200, body
    assert body['summary']['created'] == 1 and body['summary']['updated'] == 1
    assert _exec_rows(scoped_plans, 5, 10) == [
        (50, 'completed', 'uid=0(root)', '2026-10-31 10:01:01', '2026-10-31 10:01:05')]

    # Re-importing the same log is idempotent
    _import(scoped_plans, log, plan_id=5, host_id=10, apply=True)
    rows = _exec_rows(scoped_plans, 5, 10)
    assert len(rows) == 1 and rows[0][2] == 'uid=0(root)'


def test_import_appends_to_existing_output_and_never_downgrades(scoped_plans):
    c = scoped_plans.cursor()
    c.execute("""INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, host_id,
                 status, execution_output) VALUES (1, 5, 50, NULL, 'completed', 'manual notes')""")
    scoped_plans.commit()

    unfinished = _log((1, 'T1003', 'Test 3', 'START', 50, 'second attempt'))
    _import(scoped_plans, unfinished, plan_id=5, apply=True)
    (item, status, output, _, _), = _exec_rows(scoped_plans, 5, None)
    assert status == 'completed', "an unfinished log run must not downgrade a completed result"
    assert output == 'manual notes\n\n--- Imported from session log ---\nsecond attempt'


def test_import_maps_template_item_ids_onto_engagement_copy(scoped_plans):
    # Script generated from template plan 1, results imported into its engagement copy
    _, copy = _call(scoped_plans, tp_routes.duplicate_plan, method='POST', args=(1,),
                    body={'target': 'engagement'})
    log = _log((1, 'T1001', 'Test 1', 'PASS', 1, 'atomic ok'),
               (2, 'Custom', 'Custom recon', 'FAIL', 2, 'denied'))
    status, body = _import(scoped_plans, log, plan_id=copy['id'], host_id=10)
    assert status == 200, body
    assert [r['matched_by'] for r in body['results']] == ['source', 'source']
    c = scoped_plans.cursor()
    c.execute("SELECT id FROM test_plan_items WHERE test_plan_id = ? ORDER BY sort_order", (copy['id'],))
    copy_items = [r[0] for r in c.fetchall()]
    assert [r['item_id'] for r in body['results']] == copy_items


def test_import_untagged_log_matches_by_name_and_reports_unmatched(scoped_plans):
    log = _log((1, 'T1003', 'Test 3', 'PASS', None, 'ok'),
               (2, 'T9999', 'Not in this plan', 'PASS', None, 'x'),
               (3, 'T1003', 'Test 3', 'SKIP', None, ''))
    status, body = _import(scoped_plans, log, plan_id=5, apply=True)
    assert status == 200, body
    by_n = {r['test_number']: r for r in body['results']}
    assert by_n[1]['matched_by'] == 'name' and by_n[1]['item_id'] == 50
    assert by_n[2]['item_id'] is None and by_n[2]['unmatched_reason'] == 'not_in_plan'
    assert body['summary']['unmatched'] == 1
    # Test 3 (skip) also maps to item 50 and, coming later in the log, wins
    assert _exec_rows(scoped_plans, 5, None)[0][1] == 'skipped'


def test_import_does_not_follow_tags_into_other_engagements(scoped_plans):
    # item 60 belongs to engagement 2's plan; its atomic must not be used to match
    log = _log((1, 'T1004', 'Test 4', 'PASS', 60, 'x'))
    _, body = _import(scoped_plans, log, plan_id=5)
    assert body['results'][0]['item_id'] is None


@pytest.mark.parametrize('plan_id,host_id,log,expected', [
    (1, '', 'x', 400),        # template
    (6, '', 'x', 404),        # other engagement's plan
    (5, 11, 'x', 400),        # out-of-scope host
    (5, 20, 'x', 400),        # host from another engagement
    (5, '', 'just some text\nno events', 400),
])
def test_import_rejections(scoped_plans, plan_id, host_id, log, expected):
    if log == 'x':
        log = _log((1, 'T1003', 'Test 3', 'PASS', 50, 'ok'))
    status, body = _import(scoped_plans, log, plan_id=plan_id, host_id=host_id, apply=True)
    assert status == expected, body
    assert _exec_rows(scoped_plans, 5, None) == [] and _exec_rows(scoped_plans, 5, 10) == []


# ------------------------------------- items whose atomic left the library

@pytest.fixture
def plan_with_missing(scoped_plans):
    """Plan 5 (E1) gets a second item pointing at an atomic id that no longer exists."""
    c = scoped_plans.cursor()
    # Production connections don't enforce foreign keys, which is how
    # dangling atomic ids arise; reproduce that here.
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("INSERT INTO test_plan_items (id, test_plan_id, atomic_id, sort_order, enabled) VALUES (51, 5, 99999, 1, 1)")
    scoped_plans.commit()
    c.execute("PRAGMA foreign_keys = ON")
    return scoped_plans


def test_plans_report_missing_atomics(plan_with_missing):
    _, plans = _call(plan_with_missing, tp_routes.list_plans)
    by_id = {p['id']: p for p in plans}
    assert by_id[5]['item_count'] == 2 and by_id[5]['missing_count'] == 1
    assert by_id[1]['missing_count'] == 0

    status, plan = _call(plan_with_missing, tp_routes.get_plan, args=(5,))
    assert status == 200
    flags = {i['id']: i['atomic_missing'] for i in plan['items']}
    assert flags == {50: False, 51: True}
    assert 'atomic_found' not in plan['items'][0]


def test_script_generation_skips_missing_atomics(plan_with_missing):
    fn = inspect.unwrap(tp_routes.generate_script_endpoint)
    app = Flask(__name__)
    with app.test_request_context('/', query_string={'platform': 'windows', 'include_readme': 'false'}):
        g.db = plan_with_missing
        g.active_engagement_id = 1
        resp = fn(5)
    body = resp.get_data(as_text=True) if hasattr(resp, 'get_data') else resp[0].get_data(as_text=True)
    assert '[item=50]' in body
    assert '[item=51]' not in body


def test_script_generation_explains_when_every_test_is_missing(plan_with_missing):
    c = plan_with_missing.cursor()
    c.execute("UPDATE test_plan_items SET enabled = 0 WHERE id = 50")
    plan_with_missing.commit()
    fn = inspect.unwrap(tp_routes.generate_script_endpoint)
    app = Flask(__name__)
    with app.test_request_context('/', query_string={'platform': 'windows'}):
        g.db = plan_with_missing
        g.active_engagement_id = 1
        resp, status = fn(5)
    assert status == 400
    assert 'missing from the Atomics library' in resp.get_json()['error']


def test_list_plans_reports_run_progress_for_the_active_engagement(scoped_plans):
    c = scoped_plans.cursor()
    c.execute("INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, status, outcome) "
              "VALUES (1, 5, 50, 'completed', 'alerted')")
    c.execute("INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, status) "
              "VALUES (1, 5, 50, 'pending')")
    scoped_plans.commit()
    _, plans = _call(scoped_plans, tp_routes.list_plans)
    by_id = {p['id']: p for p in plans}
    assert (by_id[5]['exec_total'], by_id[5]['exec_done'], by_id[5]['exec_evaluated']) == (2, 1, 1)
    # Template plan 1's legacy executions belong to E1 too, but templates show no progress in the UI;
    # the counts are still reported accurately
    assert by_id[1]['exec_total'] == 2

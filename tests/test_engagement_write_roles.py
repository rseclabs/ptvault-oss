"""H-4: writes to the active engagement's data need the editor role.

Each write route is called with engagement A active. Owners and editors get
past authorization (the handler may still reject the placeholder ids or
body); a viewer, including a global viewer, gets 403; a non-member's session
loses A as its active engagement, so it gets 400.
"""

import re

import pytest

from tests.conftest import ENGAGEMENT_A

# Write routes that act on the active engagement, by module and function.
EDITOR_WRITES = {
    'routes.evidence': ['create_evidence', 'update_evidence', 'delete_evidence', 'parse_evidence',
                        'bulk_evidence_operation'],
    'routes.hosts': ['create_host', 'update_host', 'delete_host', 'link_evidence', 'unlink_evidence',
                     'create_note', 'update_note', 'delete_note', 'move_note', 'create_port', 'update_port',
                     'delete_port', 'create_credential', 'update_credential', 'delete_credential'],
    'routes.filters': ['create_filter', 'update_filter', 'delete_filter'],
    'routes.relationships': ['create_relationship', 'delete_relationship', 'delete_node_relationships',
                             'save_attack_path', 'delete_attack_path'],
    'routes.reporting': ['create_report', 'update_report', 'delete_report', 'apply_report_template'],
    'routes.attack_maps': ['create_map', 'update_map', 'delete_map', 'duplicate_map', 'create_node',
                           'update_node', 'delete_node', 'batch_update_nodes', 'create_edge', 'delete_edge'],
    # create_plan and duplicate_plan check inside the handler, since a plan can be
    # a template with no engagement (tests/test_shared_content_ownership.py).
    'routes.testplans': ['start_execution', 'update_execution', 'import_session_log', 'link_evidence',
                         'delete_execution'],
}
EXPECTED = {f'{module}.{name}' for module, names in EDITOR_WRITES.items() for name in names}
WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def _write_calls(app):
    """(label, method, url) for every write rule whose view is in EDITOR_WRITES."""
    calls = []
    for rule in app.url_map.iter_rules():
        view = app.view_functions[rule.endpoint]
        label = f'{view.__module__}.{view.__name__}'
        if label not in EXPECTED:
            continue
        url = re.sub(r'<(?:\w+:)?\w+>', '1', rule.rule)
        for method in sorted(rule.methods & WRITE_METHODS):
            calls.append((label, method, url))
    return calls


def test_every_listed_write_route_is_registered(live_app):
    assert {label for label, _, _ in _write_calls(live_app.app)} == EXPECTED


@pytest.mark.parametrize('user,expected', [
    ('owner', 'allowed'), ('editor', 'allowed'), ('viewer', 403), ('outsider', 400),
])
def test_write_routes_require_editor(live_app, user, expected):
    client = live_app.client_for(user, active_engagement=ENGAGEMENT_A)
    wrong = []
    for label, method, url in _write_calls(live_app.app):
        resp = client.open(url, method=method, json={})
        error = (resp.get_json(silent=True) or {}).get('error', '') if resp.is_json else ''
        if expected == 'allowed':
            blocked = resp.status_code in (401, 403) or error in ('insufficient permissions',
                                                                   'no active engagement')
            if blocked:
                wrong.append((label, method, resp.status_code, error))
        elif resp.status_code != expected:
            wrong.append((label, method, resp.status_code, error))
    assert not wrong


def test_global_viewer_with_editor_membership_still_cannot_write(live_app):
    conn = live_app.db()
    conn.execute("UPDATE engagement_members SET role = 'editor' WHERE user_id = ?", (live_app.user_ids['viewer'],))
    conn.commit()
    conn.close()
    client = live_app.client_for('viewer', active_engagement=ENGAGEMENT_A)
    resp = client.post('/api/hosts', json={'ip': '10.1.1.1'})
    assert resp.status_code == 403


def test_editor_write_reaches_the_database(live_app):
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    assert client.post('/api/hosts', json={'ip': '10.1.1.2'}).status_code in (200, 201)
    conn = live_app.db()
    assert conn.execute("SELECT engagement_id FROM hosts WHERE ip = '10.1.1.2'").fetchone()[0] == ENGAGEMENT_A
    conn.close()

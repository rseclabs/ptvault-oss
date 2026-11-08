"""H-4 (part 2): a global viewer cannot change shared content or test plans.

Writeups, commands and ATT&CK layers are shared by all users; a global
viewer is read-only, so these writes need an admin or tester. Downloading the
Atomics library is admin-only (M-6, tests/test_atomics_download.py).
A test plan belonging to an engagement needs the editor role on it; a global
plan template needs an admin or tester.
"""

import pytest

from tests.conftest import ENGAGEMENT_A, ENGAGEMENT_B

VIEWER_FORBIDDEN = [
    ('POST', '/api/reporting/writeups', {'name': 'w'}),
    ('PUT', '/api/reporting/writeups/{writeup}', {'name': 'w2'}),
    ('DELETE', '/api/reporting/writeups/{writeup}', None),
    ('POST', '/api/commands', {'category': 'c', 'name': 'n', 'command': 'id'}),
    ('PUT', '/api/commands/{command}', {'name': 'n2'}),
    ('DELETE', '/api/commands/{command}', None),
    ('POST', '/api/commands/{command}/favorite', None),
    ('POST', '/api/testplans/atomics/download', None),
    ('POST', '/api/testplans/layers/import', {}),
    ('DELETE', '/api/testplans/layers/1', None),
]


@pytest.fixture(autouse=True)
def no_atomics_download(monkeypatch):
    """Never reach the network or data/atomics, even if the role check regresses."""
    def refuse(*args, **kwargs):
        raise AssertionError('atomics download reached the downloader')
        yield  # pragma: no cover - makes this a generator like the real one
    monkeypatch.setattr('utils.atomics_downloader.download_and_parse_atomics_with_progress', refuse)


def _seed(live):
    # Shared rows are owned by the outsider (a tester), who may change them (M-1).
    conn = live.db()
    tester = live.user_ids['outsider']
    ids = {
        'writeup': conn.execute("INSERT INTO writeups (name, created_by) VALUES ('w', ?)", (tester,)).lastrowid,
        'command': conn.execute(
            "INSERT INTO commands (category, name, command, is_custom, created_by) VALUES ('c', 'n', 'id', 1, ?)",
            (tester,)).lastrowid,
        'template': conn.execute("INSERT INTO test_plans (name, created_by) VALUES ('Template', ?)",
                                 (tester,)).lastrowid,
        'plan_a': conn.execute("INSERT INTO test_plans (name, engagement_id) VALUES ('A plan', ?)",
                               (ENGAGEMENT_A,)).lastrowid,
    }
    conn.commit()
    conn.close()
    return ids


@pytest.mark.parametrize('method,path,body', VIEWER_FORBIDDEN, ids=[f'{m} {p}' for m, p, _ in VIEWER_FORBIDDEN])
def test_global_viewer_cannot_change_shared_content(live_app, method, path, body):
    ids = _seed(live_app)
    resp = live_app.client_for('viewer').open(path.format(**ids), method=method, json=body)
    assert resp.status_code == 403


def test_tester_can_change_shared_content(live_app):
    ids = _seed(live_app)
    client = live_app.client_for('outsider')
    assert client.post('/api/reporting/writeups', json={'name': 'w'}).status_code == 201
    assert client.put(f"/api/commands/{ids['command']}", json={'name': 'n2'}).status_code == 200


def test_viewer_cannot_record_command_usage(live_app):
    # Usage orders the shared command list for everyone, so a read-only account may
    # not change it (retest 2 L-28; it was allowed after M-1). The client records
    # usage best-effort, so copying still works for viewers.
    ids = _seed(live_app)
    assert live_app.client_for('viewer').post(f"/api/commands/{ids['command']}/usage").status_code == 403


@pytest.mark.parametrize('user,expected', [('admin', 200), ('outsider', 200), ('viewer', 403)])
def test_plan_template_needs_owner_or_admin(live_app, user, expected):
    ids = _seed(live_app)
    client = live_app.client_for(user)
    assert client.put(f"/api/testplans/plans/{ids['template']}", json={'name': 'x'}).status_code == expected
    reorder = client.post(f"/api/testplans/plans/{ids['template']}/items/reorder", json={'item_ids': [1]})
    if expected == 403:
        assert reorder.status_code == 403
    else:
        assert reorder.status_code not in (401, 403)


@pytest.mark.parametrize('user,expected', [('owner', 200), ('editor', 200), ('viewer', 403)])
def test_engagement_plan_needs_editor(live_app, user, expected):
    ids = _seed(live_app)
    client = live_app.client_for(user, active_engagement=ENGAGEMENT_A)
    assert client.put(f"/api/testplans/plans/{ids['plan_a']}", json={'name': 'x'}).status_code == expected
    assert client.delete(f"/api/testplans/plans/{ids['plan_a']}").status_code == expected


def test_engagement_plan_is_hidden_from_other_engagements(live_app):
    ids = _seed(live_app)
    client = live_app.client_for('outsider', active_engagement=ENGAGEMENT_B)
    assert client.put(f"/api/testplans/plans/{ids['plan_a']}", json={'name': 'x'}).status_code == 404

"""H-1 / H-2: engagement routes check access to the engagement in the URL.

Every /api/engagements/<id>/... route is called by each LIVE_USERS account
against engagement A. Non-members get 404 (the engagement's existence is not
revealed), members below the route's role get 403, and a global viewer is
read-only whatever its membership says.
"""

import pytest

from tests.conftest import ENGAGEMENT_A, ENGAGEMENT_B

A = ENGAGEMENT_A
RANK = {None: 0, 'viewer': 1, 'editor': 2, 'owner': 3}
# Role each user effectively holds on engagement A.
EFFECTIVE_ROLE = {'admin': 'owner', 'owner': 'owner', 'editor': 'editor',
                  'viewer': 'viewer', 'outsider': None}

# (method, path, minimum role, JSON body). {note}, {cred}, {dump}, {finding}
# and {member} are ids of records seeded in engagement A.
ROUTES = [
    ('GET', '/api/engagements/{a}', 'viewer', None),
    ('PUT', '/api/engagements/{a}', 'owner', {'description': 'changed'}),
    ('GET', '/api/engagements/{a}/notes', 'viewer', None),
    ('GET', '/api/engagements/{a}/notes/{note}', 'viewer', None),
    ('POST', '/api/engagements/{a}/notes', 'editor', {'content': 'n', 'title': 't'}),
    ('PUT', '/api/engagements/{a}/notes/{note}', 'editor', {'content': 'x'}),
    ('POST', '/api/engagements/{a}/notes/{note}/move', 'editor', {'parent_id': None, 'sort_order': 0}),
    ('DELETE', '/api/engagements/{a}/notes/{note}', 'editor', None),
    ('GET', '/api/engagements/{a}/export/json', 'viewer', None),
    ('GET', '/api/engagements/{a}/export/markdown', 'viewer', None),
    ('GET', '/api/engagements/{a}/credentials', 'viewer', None),
    ('POST', '/api/engagements/{a}/credentials', 'editor', {'username': 'u', 'password_or_hash': 'p'}),
    ('PUT', '/api/engagements/{a}/credentials/{cred}', 'editor', {'description': 'd'}),
    ('DELETE', '/api/engagements/{a}/credentials/{cred}', 'editor', None),
    ('GET', '/api/engagements/{a}/terminal-dumps', 'viewer', None),
    ('GET', '/api/engagements/{a}/terminal-dumps/{dump}', 'viewer', None),
    ('POST', '/api/engagements/{a}/terminal-dumps', 'editor', {'title': 't', 'content': 'c'}),
    ('PUT', '/api/engagements/{a}/terminal-dumps/{dump}', 'editor', {'title': 't2'}),
    ('DELETE', '/api/engagements/{a}/terminal-dumps/{dump}', 'editor', None),
    ('GET', '/api/engagements/{a}/findings', 'viewer', None),
    ('POST', '/api/engagements/{a}/findings', 'editor', {'title': 'f', 'criticality': 'low'}),
    ('PUT', '/api/engagements/{a}/findings/{finding}', 'editor', {'title': 'f2'}),
    ('POST', '/api/engagements/{a}/findings/{finding}/toggle-report', 'editor', None),
    ('DELETE', '/api/engagements/{a}/findings/{finding}', 'editor', None),
    ('GET', '/api/engagements/{a}/members', 'viewer', None),
    ('POST', '/api/engagements/{a}/members', 'owner', {'user_id': '{outsider_id}', 'role': 'viewer'}),
    ('PUT', '/api/engagements/{a}/members/{member}', 'owner', {'role': 'viewer'}),
    ('DELETE', '/api/engagements/{a}/members/{member}', 'owner', None),
]


def _seed(live):
    conn = live.db()
    ids = {'a': A, 'outsider_id': live.user_ids['outsider']}
    ids['note'] = conn.execute(
        "INSERT INTO engagement_notes (engagement_id, title, content) VALUES (?, 'n', 'c')", (A,)).lastrowid
    ids['cred'] = conn.execute(
        "INSERT INTO engagement_credentials (engagement_id, username, password_or_hash) VALUES (?, 'u', 'p')",
        (A,)).lastrowid
    ids['dump'] = conn.execute(
        "INSERT INTO terminal_dumps (engagement_id, title, content) VALUES (?, 't', 'c')", (A,)).lastrowid
    ids['finding'] = conn.execute(
        "INSERT INTO engagement_findings (engagement_id, title, criticality) VALUES (?, 'f', 'low')",
        (A,)).lastrowid
    # A spare member whose role the owner-only routes change or remove.
    spare = conn.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES ('spare', 'spare@example.com', 'x', 'tester')"
    ).lastrowid
    ids['member'] = conn.execute(
        "INSERT INTO engagement_members (engagement_id, user_id, role) VALUES (?, ?, 'editor')", (A, spare)
    ).lastrowid
    conn.commit()
    conn.close()
    return ids


def _fill(value, ids):
    if isinstance(value, str):
        filled = value.format(**ids)
        return int(filled) if value.startswith('{') and filled.isdigit() else filled
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


@pytest.mark.parametrize('user', list(EFFECTIVE_ROLE))
@pytest.mark.parametrize('method,path,min_role,body', ROUTES,
                         ids=[f'{m} {p}' for m, p, _, _ in ROUTES])
def test_route_enforces_engagement_role(live_app, user, method, path, min_role, body):
    ids = _seed(live_app)
    client = live_app.client_for(user)
    resp = client.open(path.format(**ids), method=method, json=_fill(body, ids))
    role = EFFECTIVE_ROLE[user]

    if role is None:
        assert resp.status_code == 404, resp.get_json()
    elif RANK[role] < RANK[min_role]:
        assert resp.status_code == 403, resp.get_json()
    else:
        assert resp.status_code < 400, resp.get_json()


def test_member_of_another_engagement_cannot_make_itself_owner(live_app):
    # H-2: the outsider owns B and has it active; the owner check must use A.
    client = live_app.client_for('outsider', active_engagement=ENGAGEMENT_B)
    resp = client.post(f'/api/engagements/{A}/members',
                       json={'user_id': live_app.user_ids['outsider'], 'role': 'owner'})
    assert resp.status_code == 404
    conn = live_app.db()
    assert conn.execute('SELECT COUNT(*) FROM engagement_members WHERE engagement_id = ? AND user_id = ?',
                        (A, live_app.user_ids['outsider'])).fetchone()[0] == 0
    conn.close()


def test_global_viewer_is_read_only_even_as_engagement_owner(live_app):
    conn = live_app.db()
    conn.execute("UPDATE engagement_members SET role = 'owner' WHERE user_id = ?", (live_app.user_ids['viewer'],))
    conn.commit()
    conn.close()
    client = live_app.client_for('viewer')
    assert client.get(f'/api/engagements/{A}/credentials').status_code == 200
    assert client.post(f'/api/engagements/{A}/credentials',
                       json={'username': 'u', 'password_or_hash': 'p'}).status_code == 403
    assert client.put(f'/api/engagements/{A}', json={'description': 'x'}).status_code == 403


@pytest.mark.parametrize('path', ['/api/engagements', '/api/engagements/import'])
def test_global_viewer_cannot_create_engagements(live_app, path):
    resp = live_app.client_for('viewer').post(path, json={'name': 'New', 'client_name': 'C'})
    assert resp.status_code == 403


def test_tester_can_create_engagement_and_owns_it(live_app):
    resp = live_app.client_for('outsider').post('/api/engagements', json={'name': 'New', 'client_name': 'C'})
    assert resp.status_code == 201
    new_id = resp.get_json()['id']
    assert live_app.client_for('outsider').get(f'/api/engagements/{new_id}/credentials').status_code == 200


def test_missing_engagement_is_404_for_admin(live_app):
    assert live_app.client_for('admin').get('/api/engagements/9999/credentials').status_code == 404

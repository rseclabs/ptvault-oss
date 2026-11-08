"""M-3: authorization state comes from the database on every request.

The JWT says who the user is; their role, whether the account is active and
whether they may still use their active engagement are read fresh, so a
disabled, demoted or removed user loses access at once.
"""

from tests.conftest import ENGAGEMENT_A

ADMIN_ONLY = '/api/users'
ACTIVE_ENGAGEMENT_ROUTE = '/api/hosts'


def _sql(live, statement, params=()):
    conn = live.db()
    conn.execute(statement, params)
    conn.commit()
    conn.close()


def test_disabled_account_is_refused(live_app):
    client = live_app.client_for('owner')
    assert client.get('/api/engagements').status_code == 200
    _sql(live_app, 'UPDATE users SET is_active = 0 WHERE id = ?', (live_app.user_ids['owner'],))
    assert client.get('/api/engagements').status_code == 401


def test_deleted_account_is_refused(live_app):
    client = live_app.client_for('editor')
    _sql(live_app, 'DELETE FROM engagement_members WHERE user_id = ?', (live_app.user_ids['editor'],))
    _sql(live_app, 'DELETE FROM users WHERE id = ?', (live_app.user_ids['editor'],))
    assert client.get('/api/engagements').status_code == 401


def test_demoted_admin_loses_admin_routes(live_app):
    client = live_app.client_for('admin')
    assert client.get(ADMIN_ONLY).status_code == 200
    _sql(live_app, "UPDATE users SET role = 'tester' WHERE id = ?", (live_app.user_ids['admin'],))
    assert client.get(ADMIN_ONLY).status_code == 403


def test_promoted_user_gains_admin_routes(live_app):
    client = live_app.client_for('editor')
    assert client.get(ADMIN_ONLY).status_code == 403
    _sql(live_app, "UPDATE users SET role = 'admin' WHERE id = ?", (live_app.user_ids['editor'],))
    assert client.get(ADMIN_ONLY).status_code == 200


def test_removed_member_loses_active_engagement(live_app):
    _sql(live_app, "INSERT INTO hosts (engagement_id, ip, hostname) VALUES (?, '10.0.0.5', 'secret-host')",
         (ENGAGEMENT_A,))
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    assert b'secret-host' in client.get(ACTIVE_ENGAGEMENT_ROUTE).data

    _sql(live_app, 'DELETE FROM engagement_members WHERE user_id = ?', (live_app.user_ids['editor'],))
    resp = client.get(ACTIVE_ENGAGEMENT_ROUTE)
    assert resp.status_code == 400
    assert b'secret-host' not in resp.data


def test_forged_active_engagement_in_session_is_ignored(live_app):
    # The outsider is not a member of A; a session claiming A is not honoured.
    _sql(live_app, "INSERT INTO hosts (engagement_id, ip, hostname) VALUES (?, '10.0.0.6', 'a-only-host')",
         (ENGAGEMENT_A,))
    client = live_app.client_for('outsider', active_engagement=ENGAGEMENT_A)
    resp = client.get(ACTIVE_ENGAGEMENT_ROUTE)
    assert resp.status_code == 400
    assert b'a-only-host' not in resp.data


def test_team_member_keeps_active_engagement(live_app):
    outsider = live_app.user_ids['outsider']
    _sql(live_app, "INSERT INTO teams (id, name) VALUES (7, 'Red team')")
    _sql(live_app, "INSERT INTO team_members (team_id, user_id, role) VALUES (7, ?, 'member')", (outsider,))
    _sql(live_app, 'UPDATE engagements SET team_id = 7 WHERE id = ?', (ENGAGEMENT_A,))
    client = live_app.client_for('outsider', active_engagement=ENGAGEMENT_A)
    assert client.get(ACTIVE_ENGAGEMENT_ROUTE).status_code == 200

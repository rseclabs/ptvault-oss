"""H-3: an engagement can only be moved to a team the caller belongs to.

Team membership grants access to the team's engagements, so setting
team_id is a grant. Only an admin, or a member of the target team, may set
it (on create, or as the engagement's owner on update); clearing it is
allowed for the owner.
"""

import pytest

from tests.conftest import ENGAGEMENT_A

OWN_TEAM, OTHER_TEAM = 10, 20


@pytest.fixture
def teams(live_app):
    conn = live_app.db()
    conn.execute("INSERT INTO teams (id, name) VALUES (?, 'Owner team'), (?, 'Other team')",
                 (OWN_TEAM, OTHER_TEAM))
    conn.execute("INSERT INTO team_members (team_id, user_id, role) VALUES (?, ?, 'member')",
                 (OWN_TEAM, live_app.user_ids['owner']))
    conn.execute("INSERT INTO team_members (team_id, user_id, role) VALUES (?, ?, 'member')",
                 (OTHER_TEAM, live_app.user_ids['outsider']))
    conn.commit()
    conn.close()
    return live_app


def _team_of(live, engagement_id):
    conn = live.db()
    team = conn.execute('SELECT team_id FROM engagements WHERE id = ?', (engagement_id,)).fetchone()[0]
    conn.close()
    return team


def test_owner_cannot_move_engagement_to_a_team_they_are_not_in(teams):
    resp = teams.client_for('owner').put(f'/api/engagements/{ENGAGEMENT_A}', json={'team_id': OTHER_TEAM})
    assert resp.status_code == 403
    assert _team_of(teams, ENGAGEMENT_A) is None


def test_owner_can_move_engagement_to_own_team_and_clear_it(teams):
    client = teams.client_for('owner')
    assert client.put(f'/api/engagements/{ENGAGEMENT_A}', json={'team_id': OWN_TEAM}).status_code == 200
    assert _team_of(teams, ENGAGEMENT_A) == OWN_TEAM
    assert client.put(f'/api/engagements/{ENGAGEMENT_A}', json={'team_id': None}).status_code == 200
    assert _team_of(teams, ENGAGEMENT_A) is None


def test_admin_can_assign_any_team(teams):
    resp = teams.client_for('admin').put(f'/api/engagements/{ENGAGEMENT_A}', json={'team_id': OTHER_TEAM})
    assert resp.status_code == 200
    assert _team_of(teams, ENGAGEMENT_A) == OTHER_TEAM


def test_owner_outside_assigned_team_can_still_save_other_fields(teams):
    assert teams.client_for('admin').put(f'/api/engagements/{ENGAGEMENT_A}',
                                         json={'team_id': OTHER_TEAM}).status_code == 200
    resp = teams.client_for('owner').put(f'/api/engagements/{ENGAGEMENT_A}',
                                         json={'team_id': OTHER_TEAM, 'description': 'edited'})
    assert resp.status_code == 200
    assert _team_of(teams, ENGAGEMENT_A) == OTHER_TEAM


def test_unknown_team_is_rejected(teams):
    resp = teams.client_for('admin').put(f'/api/engagements/{ENGAGEMENT_A}', json={'team_id': 999})
    assert resp.status_code == 400
    assert _team_of(teams, ENGAGEMENT_A) is None


def test_non_member_cannot_move_engagement_into_their_team(teams):
    # The report's chain: the outsider moves A into their own team to gain access.
    resp = teams.client_for('outsider').put(f'/api/engagements/{ENGAGEMENT_A}', json={'team_id': OTHER_TEAM})
    assert resp.status_code == 404
    assert _team_of(teams, ENGAGEMENT_A) is None


@pytest.mark.parametrize('team_id,expected', [(OWN_TEAM, 201), (OTHER_TEAM, 403), (999, 400), (None, 201)])
def test_create_checks_team(teams, team_id, expected):
    resp = teams.client_for('owner').post('/api/engagements', json={'name': 'New', 'team_id': team_id})
    assert resp.status_code == expected

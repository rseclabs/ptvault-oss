"""Command favorites belong to each user (retest L-22, part of M-1).

is_favorite was one column on the shared commands row, so any tester could
star or unstar commands for everyone, including other users' commands.
Favorites are now rows in command_favorites(user_id, command_id).
"""

import importlib

import pytest


@pytest.fixture
def command(live_app):
    conn = live_app.db()
    command_id = conn.execute(
        "INSERT INTO commands (category, name, command, is_custom, created_by) VALUES ('Recon', 'mine', 'id', 1, ?)",
        (live_app.user_ids['owner'],)).lastrowid
    conn.commit()
    conn.close()
    live_app.command_id = command_id
    return live_app


def _favorite(client, command_id):
    return [c for c in client.get('/api/commands').get_json() if c['id'] == command_id][0]['is_favorite']


def test_a_favorite_is_only_the_users_own(command):
    owner, other = command.client_for('owner'), command.client_for('editor')
    assert other.post(f'/api/commands/{command.command_id}/favorite').get_json() == {'is_favorite': 1}
    assert _favorite(other, command.command_id) == 1
    assert _favorite(owner, command.command_id) == 0                      # not starred for anyone else

    assert owner.post(f'/api/commands/{command.command_id}/favorite').get_json() == {'is_favorite': 1}
    assert other.post(f'/api/commands/{command.command_id}/favorite').get_json() == {'is_favorite': 0}
    assert _favorite(owner, command.command_id) == 1                      # another user's toggle does not touch it
    assert command.command_id in [c['id'] for c in owner.get('/api/commands?is_favorite=true').get_json()]
    assert command.command_id not in [c['id'] for c in other.get('/api/commands?is_favorite=true').get_json()]
    assert owner.get(f'/api/commands/{command.command_id}').get_json()['is_favorite'] == 1
    assert other.get(f'/api/commands/{command.command_id}').get_json()['is_favorite'] == 0


def test_the_shared_flag_is_no_longer_written(command):
    command.client_for('editor').post(f'/api/commands/{command.command_id}/favorite')
    conn = command.db()
    shared = conn.execute('SELECT is_favorite FROM commands WHERE id = ?', (command.command_id,)).fetchone()[0]
    conn.close()
    assert shared == 0


def test_deleting_a_command_removes_its_favorites(command):
    owner = command.client_for('owner')
    owner.post(f'/api/commands/{command.command_id}/favorite')
    assert owner.delete(f'/api/commands/{command.command_id}').status_code == 200
    conn = command.db()
    left = conn.execute('SELECT COUNT(*) FROM command_favorites WHERE command_id = ?', (command.command_id,)).fetchone()[0]
    conn.close()
    assert left == 0


def test_migration_gives_each_flag_to_the_commands_creator(test_db):
    conn = test_db
    migration = importlib.import_module('models.migrations.versions.035_per_user_command_favorites')
    migration.downgrade(conn)
    conn.execute("INSERT INTO users (id, username, email, password_hash, role) VALUES "
                 "(1, 'admin', 'a@x.co', 'h', 'admin'), (2, 'tess', 't@x.co', 'h', 'tester')")
    conn.execute("INSERT INTO commands (id, category, name, command, is_favorite, created_by) VALUES "
                 "(10, 'Recon', 'by tess', 'id', 1, 2), (11, 'Recon', 'built-in', 'id', 1, NULL), "
                 "(12, 'Recon', 'not starred', 'id', 0, 2)")
    conn.commit()
    migration.upgrade(conn)
    migration.upgrade(conn)                                               # safe to repeat
    rows = sorted(tuple(r) for r in conn.execute('SELECT user_id, command_id FROM command_favorites'))
    assert rows == [(1, 11), (2, 10)]                                     # built-ins go to admins
    assert conn.execute('SELECT SUM(is_favorite) FROM commands').fetchone()[0] == 0

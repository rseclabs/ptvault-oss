"""Logs never carry stored values (retest L-18).

Every BaseDAO call logged "Executing: {query} with values: {values}" at DEBUG,
and a source run logged at DEBUG because ENVIRONMENT defaults to development,
so password hashes, client details and writeups landed in terminal and file
logs outside the encrypted database. Statements are now logged without their
values, and DEBUG needs PTVAULT_DEBUG.
"""

import logging

import pytest

SECRET_HASH = '$argon2id$v=19$m=65536,t=3,p=4$secret-hash-value'


def test_dao_calls_log_no_values(app_ctx, caplog):
    from models.dao.base import BaseDAO
    app_ctx.execute("INSERT INTO users (id, username, email, password_hash, role) "
                    "VALUES (2, 'tess', 't@x.co', 'h', 'tester')")
    dao = BaseDAO('users', engagement_scoped=False)
    with caplog.at_level(logging.DEBUG, logger='models.dao.base'):
        assert dao.update(2, {'password_hash': SECRET_HASH})
        dao.find_all({'email': 't@x.co'})
        dao.find_one({'password_hash': SECRET_HASH})
        dao.count({'email': 't@x.co'})
        dao.exists({'email': 't@x.co'})
        dao.find_by_id(2)
        new_id = dao.create({'username': 'new', 'email': 'secret@client.example', 'password_hash': SECRET_HASH,
                             'role': 'viewer'})
        dao.delete(new_id)
    assert caplog.records, 'statements are still logged'
    assert SECRET_HASH not in caplog.text and 'secret@client.example' not in caplog.text and 't@x.co' not in caplog.text


@pytest.mark.parametrize('env, expected', [
    ({}, logging.INFO),
    ({'ENVIRONMENT': 'development'}, logging.INFO),
    ({'ENVIRONMENT': 'production'}, logging.INFO),
    ({'PTVAULT_DEBUG': '1'}, logging.DEBUG),
    ({'PTVAULT_DEBUG': '0', 'ENVIRONMENT': 'development'}, logging.INFO),
])
def test_debug_logging_needs_ptvault_debug(monkeypatch, env, expected):
    from config import log_level
    for name in ('ENVIRONMENT', 'PTVAULT_DEBUG'):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert log_level() == expected


def test_routes_log_ids_not_client_names(live_app, caplog):
    """Retest 2 L-37: client, user and attack path names were logged at INFO."""
    from tests.conftest import ENGAGEMENT_A
    marker = 'AcmeSecretClientName'
    admin = live_app.client_for('admin', active_engagement=ENGAGEMENT_A)
    with caplog.at_level(logging.INFO):
        client = admin.post('/api/clients', json={'name': marker}).get_json()
        admin.delete(f"/api/clients/{client['id']}")
        admin.post('/api/users', json={'username': marker.lower(), 'email': 'm@x.co', 'full_name': marker,
                                       'password': 'Marker-Passphrase-123', 'role': 'viewer'})
        conn = live_app.db()
        ev = conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (?, 'note', 'e')",
                          (ENGAGEMENT_A,)).lastrowid
        conn.commit()
        conn.close()
        admin.post('/api/relationships/paths', json={'name': marker, 'start_id': ev, 'end_id': ev,
                                                     'path_data': [{'id': ev}]})
    assert marker not in caplog.text and marker.lower() not in caplog.text

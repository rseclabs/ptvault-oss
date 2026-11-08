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

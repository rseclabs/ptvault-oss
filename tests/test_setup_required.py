"""setup_required() decides whether / shows the setup wizard or the login page.

The database file exists from the first startup (init_db creates it), so the
decision must come from whether a user account exists, not from the file.
"""

import sqlite3

import models.database as database


def _db_with_users(path, count):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
    for n in range(count):
        conn.execute("INSERT INTO users (email) VALUES (?)", (f"user{n}@example.com",))
    conn.commit()
    conn.close()


def test_setup_required_when_no_user_exists(tmp_path, monkeypatch):
    path = str(tmp_path / 'ptvault.db')
    _db_with_users(path, 0)
    monkeypatch.setattr(database, 'get_db_connection', lambda: sqlite3.connect(path))
    assert database.setup_required() is True


def test_setup_not_required_once_a_user_exists(tmp_path, monkeypatch):
    path = str(tmp_path / 'ptvault.db')
    _db_with_users(path, 1)
    monkeypatch.setattr(database, 'get_db_connection', lambda: sqlite3.connect(path))
    assert database.setup_required() is False


def test_setup_required_when_database_unreadable(monkeypatch):
    def broken():
        raise sqlite3.DatabaseError("file is not a database")
    monkeypatch.setattr(database, 'get_db_connection', broken)
    assert database.setup_required() is True


def test_setup_required_before_users_table_exists(tmp_path, monkeypatch):
    path = str(tmp_path / 'ptvault.db')
    sqlite3.connect(path).close()
    monkeypatch.setattr(database, 'get_db_connection', lambda: sqlite3.connect(path))
    assert database.setup_required() is True

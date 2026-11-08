"""Shared pytest fixtures for PTVault tests.

Fixtures use the production schema (schema.sql + all migrations) so tests
cannot pass against a hand-rolled partial schema that has drifted from prod.

DAO tests must use the `app_ctx` fixture: BaseDAO reads `g.db` via Flask's
app context, so direct attribute injection (`dao.db = conn`) does not work.
"""

import os
import re
import sys
import sqlite3

import pytest

# Make project root importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.migrations import apply_migrations  # noqa: E402


SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'schema.sql')
REAL_DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', 'data'))


def _data_dir_snapshot():
    snapshot = {}
    for dirpath, _, filenames in os.walk(REAL_DATA_DIR):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            snapshot[os.path.relpath(path, REAL_DATA_DIR)] = (st.st_size, st.st_mtime_ns)
    return snapshot


@pytest.fixture(scope='session', autouse=True)
def real_data_dir_untouched():
    """Fail the run if any test creates, changes or deletes a file in the real data/
    folder (database, keys, uploads). Tests must point every path at tmp_path."""
    before = _data_dir_snapshot()
    yield
    after = _data_dir_snapshot()
    changed = sorted(set(before) ^ set(after) | {k for k in before.keys() & after.keys() if before[k] != after[k]})
    assert not changed, f'tests modified the real data/ folder: {changed}'


@pytest.fixture(autouse=True)
def isolated_upload_folder(tmp_path_factory, monkeypatch):
    """Point the upload folders away from the real data/ for every test.

    Unlock, setup and enabling encryption encrypt every file under
    Config.UPLOAD_FOLDER (M-14); a test that reached them without its own
    override would rewrite real evidence with a test key. real_data_dir_untouched
    only notices afterwards, so this prevents it. Fixtures that set their own
    UPLOAD_FOLDER still do, since they run later.
    """
    from config import Config
    folder = tmp_path_factory.mktemp('uploads')
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(folder))
    monkeypatch.setattr(Config, 'LEGACY_UPLOAD_FOLDER', str(folder))


def _split_schema_statements(schema_sql: str):
    """Split schema.sql into executable statements.

    Mirrors the parsing in models.database.init_db so triggers' BEGIN...END
    blocks are not broken on intermediate semicolons.
    """
    schema_sql = re.sub(r'--[^\n]*', '', schema_sql)

    statements = []
    current = []
    in_block = False

    for line in schema_sql.split('\n'):
        line = line.strip()
        if not line:
            continue
        current.append(line)
        if 'BEGIN' in line.upper():
            in_block = True
        elif 'END;' in line.upper() and in_block:
            in_block = False
            statements.append(' '.join(current))
            current = []
        elif line.endswith(';') and not in_block:
            statements.append(' '.join(current))
            current = []

    return [s for s in statements if s.strip()]


def _add_generated_columns(cursor):
    """Add the tool_name and severity_level generated columns.

    These are added by init_db at runtime (not in schema.sql) for compatibility
    with older databases. Tests need them too so DAO/parser code that reads
    them works against the test DB.
    """
    cursor.execute(
        "SELECT COUNT(*) FROM pragma_table_info('evidence') "
        "WHERE name IN ('tool_name', 'severity_level')"
    )
    if cursor.fetchone()[0] != 0:
        return

    cursor.execute('''
        ALTER TABLE evidence
        ADD COLUMN tool_name TEXT GENERATED ALWAYS AS (
            json_extract(metadata, '$.tool')
        ) STORED
    ''')
    cursor.execute('''
        ALTER TABLE evidence
        ADD COLUMN severity_level TEXT GENERATED ALWAYS AS (
            CASE
                WHEN CAST(json_extract(metadata, '$.summary.by_severity.Critical') AS INTEGER) > 0 THEN 'critical'
                WHEN CAST(json_extract(metadata, '$.summary.by_severity.High') AS INTEGER) > 0 THEN 'high'
                WHEN CAST(json_extract(metadata, '$.summary.by_severity.Medium') AS INTEGER) > 0 THEN 'medium'
                WHEN CAST(json_extract(metadata, '$.summary.by_severity.Low') AS INTEGER) > 0 THEN 'low'
                ELSE NULL
            END
        ) STORED
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_evidence_tool_name ON evidence(tool_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_evidence_severity ON evidence(severity_level)')


def _init_test_db(conn):
    """Apply schema.sql + generated columns + all migrations to a fresh conn."""
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()

    cursor = conn.cursor()
    for stmt in _split_schema_statements(schema_sql):
        cursor.execute(stmt)

    _add_generated_columns(cursor)
    conn.commit()

    apply_migrations(conn)


@pytest.fixture
def test_db():
    """In-memory SQLite DB with full production schema and migrations applied.

    Use directly for tests that work with raw SQL or for setup. DAO tests
    should depend on `app_ctx` instead, which provides this DB inside a
    Flask app context.
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    _init_test_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def app_ctx(test_db):
    """Flask app context with g.db / g.user_id / g.active_engagement_id set.

    Required for any test that touches a BaseDAO subclass, since BaseDAO
    reads `g.db` via property. Yields the underlying connection so tests
    can also do raw SQL setup. Also seeds a default user (id=1) so
    created_by=1 foreign keys hold without per-test setup.
    """
    from flask import Flask, g

    cursor = test_db.cursor()
    cursor.execute('''
        INSERT INTO users (id, username, email, full_name, password_hash, role)
        VALUES (1, 'testuser', 'test@example.com', 'Test User', 'fake_hash_for_tests', 'admin')
    ''')
    test_db.commit()

    app = Flask(__name__)
    with app.app_context():
        g.db = test_db
        g.user_id = 1
        g.current_user = {'id': 1, 'username': 'testuser', 'role': 'admin'}
        g.current_user_role = 'admin'
        g.active_engagement_id = 1
        yield test_db


@pytest.fixture
def sample_engagement(app_ctx):
    """Create a sample engagement with hosts, findings, and evidence.

    Depends on app_ctx (which seeds the default user) so created_by FKs work.
    Returns:
        int: ID of created engagement.
    """
    cursor = app_ctx.cursor()

    cursor.execute('''
        INSERT INTO engagements (id, name, client_name, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (1, 'Test Engagement', 'ACME Corp', '2024-01-01', '2024-01-15', 'active'))
    engagement_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO hosts (engagement_id, ip, hostname, os)
        VALUES (?, ?, ?, ?)
    ''', (engagement_id, '192.168.1.10', 'server1', 'Ubuntu 20.04'))

    cursor.execute('''
        INSERT INTO hosts (engagement_id, ip, hostname, os)
        VALUES (?, ?, ?, ?)
    ''', (engagement_id, '192.168.1.20', 'server2', 'Windows Server 2019'))

    cursor.execute('''
        INSERT INTO engagement_findings
        (engagement_id, title, criticality, cvss_score, finding_content, remediation_content)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        engagement_id,
        'SQL Injection',
        'critical',
        9.8,
        'SQL injection vulnerability found in login form',
        'Use parameterized queries',
    ))

    cursor.execute('''
        INSERT INTO engagement_findings
        (engagement_id, title, criticality, cvss_score, finding_content, remediation_content)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        engagement_id,
        'Weak Password Policy',
        'medium',
        5.3,
        'Password policy allows weak passwords',
        'Implement strong password requirements',
    ))

    cursor.execute('''
        INSERT INTO evidence (engagement_id, title, evidence_type, content)
        VALUES (?, ?, ?, ?)
    ''', (engagement_id, 'Nmap Scan Results', 'command_output', 'PORT STATE SERVICE\n22/tcp open ssh'))

    cursor.execute('''
        INSERT INTO evidence (engagement_id, title, evidence_type, content)
        VALUES (?, ?, ?, ?)
    ''', (engagement_id, 'Admin Panel Access', 'screenshot', 'Successfully accessed admin panel'))

    app_ctx.commit()

    return engagement_id


# ---------------------------------------------------------------- live app

# Five users exercise every authorization path: a global admin, the owner,
# editor and viewer of engagement A, and an outsider who owns engagement B
# and has no access to A. Values are (global role, role on engagement A).
LIVE_USERS = {
    'admin': ('admin', None),
    'owner': ('tester', 'owner'),
    'editor': ('tester', 'editor'),
    'viewer': ('viewer', 'viewer'),
    'outsider': ('tester', None),
}
ENGAGEMENT_A = 1
ENGAGEMENT_B = 2


class LiveApp:
    """The real blueprints and auth middleware over a temporary database.

    `client_for(name)` returns a test client logged in as one of LIVE_USERS,
    with a session row exactly as /api/auth/login creates it. CSRF is not
    enforced here; tests/test_security.py covers it.
    """

    def __init__(self, app, db_path):
        self.app = app
        self.db_path = db_path
        self.user_ids = {}

    def db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def token_for(self, name):
        from models.auth import create_session_record, create_session_token
        role = LIVE_USERS[name][0]
        token = create_session_token(self.user_ids[name], role=role, username=name)
        conn = self.db()
        create_session_record(conn, self.user_ids[name], token)
        conn.close()
        return token

    def client_for(self, name, active_engagement=None):
        client = self.app.test_client()
        client.set_cookie('auth_token', self.token_for(name))
        if active_engagement is not None:
            with client.session_transaction() as sess:
                sess['active_engagement_id'] = active_engagement
        return client


@pytest.fixture
def live_app(tmp_path, monkeypatch):
    from flask import Flask, g
    from config import Config, BASE_DIR
    from features import register_blueprints
    from models import encryption

    monkeypatch.setattr(encryption, '_SQLCIPHER_AVAILABLE', False)
    monkeypatch.setattr(Config, 'ENCRYPTION_KEY_FILE', str(tmp_path / 'no.key'))
    monkeypatch.setattr(Config, 'ENCRYPTION_SALT_FILE', str(tmp_path / 'no.salt'))
    monkeypatch.setattr(Config, 'DATABASE_PATH', str(tmp_path / 'live.db'))
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path / 'uploads'))

    conn = sqlite3.connect(Config.DATABASE_PATH)
    _init_test_db(conn)
    live_ids = {}
    for name, (global_role, _) in LIVE_USERS.items():
        cur = conn.execute(
            'INSERT INTO users (username, email, full_name, password_hash, role) VALUES (?, ?, ?, ?, ?)',
            (name, f'{name}@example.com', name.title(), 'unused', global_role))
        live_ids[name] = cur.lastrowid
    conn.execute("INSERT INTO engagements (id, name, client_name) VALUES (?, 'Engagement A', 'Client A')",
                 (ENGAGEMENT_A,))
    conn.execute("INSERT INTO engagements (id, name, client_name) VALUES (?, 'Engagement B', 'Client B')",
                 (ENGAGEMENT_B,))
    for name, (_, eng_role) in LIVE_USERS.items():
        if eng_role:
            conn.execute('INSERT INTO engagement_members (engagement_id, user_id, role) VALUES (?, ?, ?)',
                         (ENGAGEMENT_A, live_ids[name], eng_role))
    conn.execute("INSERT INTO engagement_members (engagement_id, user_id, role) VALUES (?, ?, 'owner')",
                 (ENGAGEMENT_B, live_ids['outsider']))
    conn.commit()
    conn.close()

    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'),
                static_folder=os.path.join(BASE_DIR, 'static'))
    app.config['SECRET_KEY'] = 'live-app-test-secret-key-not-for-production'
    app.config['TESTING'] = True

    # Some route tests reload route modules under a stubbed require_auth and
    # leave them that way; reload every route module against the real
    # middleware so this app runs the real authorization checks.
    import importlib
    from features import BLUEPRINTS
    for module_path, _ in BLUEPRINTS:
        importlib.reload(importlib.import_module(module_path))
    register_blueprints(app)

    @app.teardown_appcontext
    def close_db(error):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    live = LiveApp(app, Config.DATABASE_PATH)
    live.user_ids = live_ids
    return live

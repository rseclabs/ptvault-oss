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

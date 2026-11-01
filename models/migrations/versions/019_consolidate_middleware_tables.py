"""
Migration 019: Consolidate middleware auth inline tables

Ensures all tables that were previously created inline in middleware/auth.py
exist in the proper migration system. These tables use CREATE TABLE IF NOT EXISTS
so this migration is safe to run on existing databases.

Also adds last_active and is_active columns to user_sessions for server-side
session management and revocation support.

Created: 2026-02-24
"""


def upgrade(db):
    """Apply consolidation migration."""
    cursor = db.cursor()

    print("  → Ensuring host_notes table exists")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS host_notes (
            id INTEGER PRIMARY KEY,
            host_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(host_id) REFERENCES hosts(id) ON DELETE CASCADE
        )
    ''')

    print("  → Ensuring host_ports table exists")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS host_ports (
            id INTEGER PRIMARY KEY,
            host_id INTEGER NOT NULL,
            port INTEGER NOT NULL,
            protocol TEXT DEFAULT 'tcp',
            state TEXT DEFAULT 'open',
            service TEXT,
            version TEXT,
            source TEXT DEFAULT 'manual',
            evidence_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(host_id) REFERENCES hosts(id) ON DELETE CASCADE,
            FOREIGN KEY(evidence_id) REFERENCES evidence(id) ON DELETE SET NULL,
            UNIQUE(host_id, port, protocol)
        )
    ''')

    print("  → Ensuring host_credentials table exists")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS host_credentials (
            id INTEGER PRIMARY KEY,
            host_id INTEGER NOT NULL,
            username TEXT,
            password TEXT,
            password_type TEXT DEFAULT 'cleartext',
            hash_type TEXT,
            service TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(host_id) REFERENCES hosts(id) ON DELETE CASCADE
        )
    ''')

    print("  → Ensuring engagement_notes table exists")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_notes (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
        )
    ''')

    print("  → Ensuring engagement_credentials table exists")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_credentials (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER NOT NULL,
            username TEXT,
            password_or_hash TEXT,
            credential_type TEXT DEFAULT 'clear_text',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
        )
    ''')

    print("  → Ensuring terminal_dumps table exists")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS terminal_dumps (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            session_datetime TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
        )
    ''')

    print("  → Ensuring engagement_findings table exists")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_findings (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            ip_address TEXT,
            hostname TEXT,
            criticality TEXT DEFAULT 'medium',
            cvss_score REAL,
            finding_content TEXT,
            remediation_content TEXT,
            include_in_report INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(engagement_id) REFERENCES engagements(id) ON DELETE CASCADE
        )
    ''')

    print("  → Adding last_active and is_active columns to user_sessions")
    # Add last_active column if it does not already exist
    try:
        cursor.execute('ALTER TABLE user_sessions ADD COLUMN last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    except Exception:
        pass  # Column already exists

    # Add is_active column if it does not already exist
    try:
        cursor.execute('ALTER TABLE user_sessions ADD COLUMN is_active INTEGER DEFAULT 1')
    except Exception:
        pass  # Column already exists

    # Mark all existing sessions as active so they are not inadvertently revoked
    cursor.execute('UPDATE user_sessions SET is_active = 1 WHERE is_active IS NULL')

    print("  → Creating indexes")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_host_notes_host ON host_notes(host_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_host_ports_host ON host_ports(host_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_host_credentials_host ON host_credentials(host_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_engagement_notes_engagement ON engagement_notes(engagement_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_engagement_credentials_engagement ON engagement_credentials(engagement_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_terminal_dumps_engagement ON terminal_dumps(engagement_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_engagement_findings_engagement ON engagement_findings(engagement_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active)')

    db.commit()
    print("  -> Middleware table consolidation completed")


def downgrade(db):
    """No downgrade needed - tables are IF NOT EXISTS and column additions are safe."""
    pass

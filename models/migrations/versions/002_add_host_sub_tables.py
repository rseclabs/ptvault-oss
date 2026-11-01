"""
Migration 002: Add Host Sub-Tables

Adds supporting tables for host management:
- host_notes: Markdown notes per host
- host_ports: Port scan results
- host_credentials: Discovered credentials

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Migration: Add host_notes table
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

    # Migration: Add host_ports table
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

    # Migration: Add host_credentials table
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

    # Add indexes for new tables
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_host_notes_host ON host_notes(host_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_host_ports_host ON host_ports(host_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_host_credentials_host ON host_credentials(host_id)')

    db.commit()
    print("  ✓ Host sub-tables created")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    # Drop tables in reverse order
    cursor.execute('DROP TABLE IF EXISTS host_credentials')
    cursor.execute('DROP TABLE IF EXISTS host_ports')
    cursor.execute('DROP TABLE IF EXISTS host_notes')

    db.commit()
    print("  ✓ Host sub-tables removed")

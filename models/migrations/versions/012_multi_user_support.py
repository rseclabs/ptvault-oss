"""
Migration 012: Multi-User Support with RBAC

Transforms PTVault from single-user to multi-user with role-based access control.

Features:
- Redesigned users table with username, email, role
- Engagement member management (team assignments)
- Audit logging for security and compliance
- User session tracking

Roles:
- admin: Full system access, user management
- tester: Can create engagements, full access to assigned engagements
- viewer: Read-only access to assigned engagements

Created: 2026-02-09
"""


def upgrade(db):
    """Apply multi-user support migration."""
    cursor = db.cursor()

    print("  → Migrating users table to multi-user schema")

    # Check if the users table already has the new schema (fresh install)
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'username' in columns and 'role' in columns:
        print("  ℹ Users table already has multi-user schema, ensuring supporting tables exist")
        # Still need to create supporting tables if they don't exist
        _ensure_supporting_tables(cursor, db)
        return

    # Step 1: Backup existing user (will become admin)
    cursor.execute("SELECT id, master_password_hash, created_at FROM users LIMIT 1")
    existing_user = cursor.fetchone()

    # Step 2: Rename old users table
    cursor.execute("ALTER TABLE users RENAME TO users_old")

    # Step 3: Create new users table with multi-user schema
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'tester',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    # Step 4: Migrate existing user as admin
    if existing_user:
        cursor.execute('''
            INSERT INTO users (id, username, email, full_name, password_hash, role, is_active, created_at)
            VALUES (?, 'admin', 'admin@ptvault.local', 'Administrator', ?, 'admin', 1, ?)
        ''', (existing_user[0], existing_user[1], existing_user[2]))
        print(f"  ✓ Migrated existing user (id={existing_user[0]}) to admin")
    else:
        print("  ℹ No existing user to migrate")

    # Step 5: Drop old users table
    cursor.execute("DROP TABLE users_old")

    # Step 6: Create engagement_members table (team assignments)
    print("  → Creating engagement_members table")
    cursor.execute('''
        CREATE TABLE engagement_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'tester',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by INTEGER,
            UNIQUE(engagement_id, user_id),
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (added_by) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE INDEX idx_engagement_members_engagement
        ON engagement_members(engagement_id)
    ''')

    cursor.execute('''
        CREATE INDEX idx_engagement_members_user
        ON engagement_members(user_id)
    ''')

    # Step 7: Add admin as owner of all existing engagements
    if existing_user:
        cursor.execute('''
            INSERT INTO engagement_members (engagement_id, user_id, role, added_by)
            SELECT id, ?, 'owner', ?
            FROM engagements
        ''', (existing_user[0], existing_user[0]))
        print(f"  ✓ Added admin as owner of {cursor.rowcount} existing engagement(s)")

    # Step 8: Create audit_log table
    print("  → Creating audit_log table")
    cursor.execute('''
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            engagement_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (engagement_id) REFERENCES engagements(id)
        )
    ''')

    cursor.execute('CREATE INDEX idx_audit_user ON audit_log(user_id, timestamp DESC)')
    cursor.execute('CREATE INDEX idx_audit_engagement ON audit_log(engagement_id, timestamp DESC)')
    cursor.execute('CREATE INDEX idx_audit_action ON audit_log(action, timestamp DESC)')

    # Step 9: Create user_sessions table (track active sessions)
    print("  → Creating user_sessions table")
    cursor.execute('''
        CREATE TABLE user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('CREATE INDEX idx_sessions_user ON user_sessions(user_id)')
    cursor.execute('CREATE INDEX idx_sessions_token ON user_sessions(token_hash)')
    cursor.execute('CREATE INDEX idx_sessions_expires ON user_sessions(expires_at)')

    db.commit()
    print("  ✓ Multi-user support migration completed")


def _ensure_supporting_tables(cursor, db):
    """Create supporting tables if they don't exist (for fresh installs where schema.sql already has the new users table)."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='engagement_members'")
    if not cursor.fetchone():
        print("  → Creating engagement_members table")
        cursor.execute('''
            CREATE TABLE engagement_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engagement_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'tester',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by INTEGER,
                UNIQUE(engagement_id, user_id),
                FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (added_by) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_engagement_members_engagement ON engagement_members(engagement_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_engagement_members_user ON engagement_members(user_id)')

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
    if not cursor.fetchone():
        print("  → Creating audit_log table")
        cursor.execute('''
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                engagement_id INTEGER,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id INTEGER,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (engagement_id) REFERENCES engagements(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, timestamp DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_engagement ON audit_log(engagement_id, timestamp DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, timestamp DESC)')

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_sessions'")
    if not cursor.fetchone():
        print("  → Creating user_sessions table")
        cursor.execute('''
            CREATE TABLE user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at)')

    db.commit()
    print("  ✓ Supporting tables ensured")


def downgrade(db):
    """
    Rollback multi-user support migration.

    WARNING: This will:
    - Convert back to single-user mode
    - Remove all users except the first admin
    - Remove all engagement member assignments
    - Remove all audit logs and session tracking
    """
    cursor = db.cursor()

    print("  → Rolling back multi-user support")

    # Step 1: Get the first admin user
    cursor.execute("SELECT id, password_hash, created_at FROM users WHERE role = 'admin' LIMIT 1")
    admin_user = cursor.fetchone()

    if not admin_user:
        raise Exception("No admin user found - cannot rollback safely")

    # Step 2: Create old-style users table
    cursor.execute("ALTER TABLE users RENAME TO users_new")

    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            master_password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Step 3: Insert admin as single user
    cursor.execute('''
        INSERT INTO users (id, master_password_hash, created_at)
        VALUES (?, ?, ?)
    ''', (admin_user[0], admin_user[1], admin_user[2]))

    # Step 4: Drop new tables
    cursor.execute("DROP TABLE users_new")
    cursor.execute("DROP TABLE engagement_members")
    cursor.execute("DROP TABLE audit_log")
    cursor.execute("DROP TABLE user_sessions")

    db.commit()
    print("  ✓ Rolled back to single-user mode")

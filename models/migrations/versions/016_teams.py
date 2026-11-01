"""
Migration 016: Teams

Adds teams and team_members tables for team-based engagement access control.
Engagements can optionally belong to a team. Team membership determines which
engagements users can access. Team leads get editor access, members get viewer
access on team engagements.

Created: 2026-02-16
"""


def upgrade(db):
    """Apply teams migration."""
    cursor = db.cursor()

    print("  → Creating teams table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    print("  → Creating team_members table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('lead', 'member')),
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by INTEGER,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (added_by) REFERENCES users(id),
            UNIQUE(team_id, user_id)
        )
    ''')

    print("  → Adding team_id column to engagements")
    try:
        cursor.execute('''
            ALTER TABLE engagements ADD COLUMN team_id INTEGER REFERENCES teams(id)
        ''')
    except Exception:
        pass  # Column already exists

    print("  → Creating indexes")
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_team_members_team
        ON team_members(team_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_team_members_user
        ON team_members(user_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_engagements_team
        ON engagements(team_id)
    ''')

    db.commit()
    print("  ✓ Teams migration completed")


def downgrade(db):
    """Rollback teams migration."""
    cursor = db.cursor()

    print("  → Dropping teams tables")
    cursor.execute("DROP TABLE IF EXISTS team_members")
    cursor.execute("DROP TABLE IF EXISTS teams")

    # Note: SQLite doesn't support DROP COLUMN before 3.35.0
    # The team_id column on engagements will remain but be unused

    db.commit()
    print("  ✓ Rolled back teams migration")

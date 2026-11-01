"""
Migration 013: Evidence Relationship Mapping

Creates relationship tracking between evidence items for attack path visualization.

Features:
- Evidence relationships with typed edges (leads_to, uses, discovers, exploits, escalates)
- Attack path storage for saved graph queries
- Full graph traversal support for path finding
- Support for custom relationship labels

Created: 2026-02-09
"""


def upgrade(db):
    """Apply evidence relationships migration."""
    cursor = db.cursor()

    print("  → Creating evidence_relationships table")

    # Evidence relationships table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            source_evidence_id INTEGER NOT NULL,
            target_evidence_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,
            label TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
            FOREIGN KEY (source_evidence_id) REFERENCES evidence(id) ON DELETE CASCADE,
            FOREIGN KEY (target_evidence_id) REFERENCES evidence(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id),
            CHECK (source_evidence_id != target_evidence_id)
        )
    ''')

    # Create indexes for performance
    cursor.execute('''
        CREATE INDEX idx_relationships_engagement
        ON evidence_relationships(engagement_id)
    ''')

    cursor.execute('''
        CREATE INDEX idx_relationships_source
        ON evidence_relationships(source_evidence_id)
    ''')

    cursor.execute('''
        CREATE INDEX idx_relationships_target
        ON evidence_relationships(target_evidence_id)
    ''')

    cursor.execute('''
        CREATE INDEX idx_relationships_type
        ON evidence_relationships(relationship_type)
    ''')

    print("  → Creating attack_paths table")

    # Attack paths (saved graph queries)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            start_evidence_id INTEGER,
            end_evidence_id INTEGER,
            path_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
            FOREIGN KEY (start_evidence_id) REFERENCES evidence(id) ON DELETE SET NULL,
            FOREIGN KEY (end_evidence_id) REFERENCES evidence(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE INDEX idx_attack_paths_engagement
        ON attack_paths(engagement_id)
    ''')

    db.commit()
    print("  ✓ Evidence relationships migration completed")


def downgrade(db):
    """
    Rollback evidence relationships migration.

    WARNING: This will remove all relationship data and attack paths.
    """
    cursor = db.cursor()

    print("  → Rolling back evidence relationships")

    # Drop tables
    cursor.execute("DROP TABLE IF EXISTS evidence_relationships")
    cursor.execute("DROP TABLE IF EXISTS attack_paths")

    db.commit()
    print("  ✓ Rolled back evidence relationships")

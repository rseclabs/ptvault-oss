"""
Migration 014: Universal Node Relationships

Upgrades relationships to support ALL node types (evidence, findings, notes, credentials).
Renames evidence_relationships to node_relationships with universal node support.

Changes:
- Rename evidence_relationships → node_relationships
- Replace source_evidence_id/target_evidence_id with source_node_type/id and target_node_type/id
- Support relationships between: evidence ↔ findings ↔ notes ↔ credentials
- Attack paths store ordered sequences of any node types

Created: 2026-02-10
"""


def upgrade(db):
    """Apply universal relationships migration."""
    cursor = db.cursor()

    print("  → Creating node_relationships table")

    # New universal relationships table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            source_node_type TEXT NOT NULL,
            source_node_id INTEGER NOT NULL,
            target_node_type TEXT NOT NULL,
            target_node_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,
            label TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id),
            CHECK (source_node_type IN ('evidence', 'finding', 'note', 'credential')),
            CHECK (target_node_type IN ('evidence', 'finding', 'note', 'credential')),
            CHECK (NOT (source_node_type = target_node_type AND source_node_id = target_node_id))
        )
    ''')

    # Migrate existing evidence_relationships to new format
    print("  → Migrating existing relationships")
    cursor.execute('''
        INSERT INTO node_relationships
        (engagement_id, source_node_type, source_node_id, target_node_type, target_node_id,
         relationship_type, label, description, created_at, created_by)
        SELECT engagement_id, 'evidence', source_evidence_id, 'evidence', target_evidence_id,
               relationship_type, label, description, created_at, created_by
        FROM evidence_relationships
    ''')

    # Drop old table
    print("  → Dropping old evidence_relationships table")
    cursor.execute("DROP TABLE IF EXISTS evidence_relationships")

    # Create indexes for performance
    print("  → Creating indexes")
    cursor.execute('''
        CREATE INDEX idx_node_relationships_engagement
        ON node_relationships(engagement_id)
    ''')

    cursor.execute('''
        CREATE INDEX idx_node_relationships_source
        ON node_relationships(source_node_type, source_node_id)
    ''')

    cursor.execute('''
        CREATE INDEX idx_node_relationships_target
        ON node_relationships(target_node_type, target_node_id)
    ''')

    cursor.execute('''
        CREATE INDEX idx_node_relationships_type
        ON node_relationships(relationship_type)
    ''')

    db.commit()
    print("  ✓ Universal relationships migration completed")


def downgrade(db):
    """
    Rollback universal relationships migration.

    WARNING: This will remove all non-evidence relationships.
    """
    cursor = db.cursor()

    print("  → Rolling back to evidence_relationships")

    # Recreate old table
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

    # Migrate back only evidence-to-evidence relationships
    cursor.execute('''
        INSERT INTO evidence_relationships
        (engagement_id, source_evidence_id, target_evidence_id, relationship_type,
         label, description, created_at, created_by)
        SELECT engagement_id, source_node_id, target_node_id, relationship_type,
               label, description, created_at, created_by
        FROM node_relationships
        WHERE source_node_type = 'evidence' AND target_node_type = 'evidence'
    ''')

    # Drop new table
    cursor.execute("DROP TABLE IF EXISTS node_relationships")

    # Recreate indexes
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

    db.commit()
    print("  ✓ Rolled back to evidence_relationships")

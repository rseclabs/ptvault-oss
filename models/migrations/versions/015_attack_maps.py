"""
Migration 015: Attack Maps

Adds attack_maps, attack_map_nodes, and attack_map_edges tables for the
visual attack map builder feature. Maps allow penetration testers to diagram
how they compromised a network using custom nodes and directional edges.

Node types: action, condition, infrastructure, and/or, evidence_ref, finding_ref, host_ref
Reference nodes link to existing evidence, findings, or hosts via ref_id/ref_type.

Created: 2026-02-10
"""


def upgrade(db):
    """Apply attack maps migration."""
    cursor = db.cursor()

    print("  → Creating attack_maps table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_maps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            canvas_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')

    print("  → Creating attack_map_nodes table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_map_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id INTEGER NOT NULL,
            node_type TEXT NOT NULL,
            x REAL DEFAULT 0,
            y REAL DEFAULT 0,
            width REAL DEFAULT 220,
            height REAL DEFAULT 80,
            label TEXT,
            properties TEXT,
            ref_id INTEGER,
            ref_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (map_id) REFERENCES attack_maps(id) ON DELETE CASCADE,
            CHECK (node_type IN ('action', 'condition', 'infrastructure', 'and', 'or', 'evidence_ref', 'finding_ref', 'host_ref'))
        )
    ''')

    print("  → Creating attack_map_edges table")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_map_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id INTEGER NOT NULL,
            source_node_id INTEGER NOT NULL,
            target_node_id INTEGER NOT NULL,
            label TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (map_id) REFERENCES attack_maps(id) ON DELETE CASCADE,
            FOREIGN KEY (source_node_id) REFERENCES attack_map_nodes(id) ON DELETE CASCADE,
            FOREIGN KEY (target_node_id) REFERENCES attack_map_nodes(id) ON DELETE CASCADE
        )
    ''')

    print("  → Creating indexes")
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attack_maps_engagement
        ON attack_maps(engagement_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attack_map_nodes_map
        ON attack_map_nodes(map_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attack_map_edges_map
        ON attack_map_edges(map_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attack_map_edges_source
        ON attack_map_edges(source_node_id)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attack_map_edges_target
        ON attack_map_edges(target_node_id)
    ''')

    db.commit()
    print("  ✓ Attack maps migration completed")


def downgrade(db):
    """Rollback attack maps migration."""
    cursor = db.cursor()

    print("  → Dropping attack maps tables")
    cursor.execute("DROP TABLE IF EXISTS attack_map_edges")
    cursor.execute("DROP TABLE IF EXISTS attack_map_nodes")
    cursor.execute("DROP TABLE IF EXISTS attack_maps")

    db.commit()
    print("  ✓ Rolled back attack maps migration")

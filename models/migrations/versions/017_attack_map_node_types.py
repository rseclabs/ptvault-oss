"""
Migration 017: Update Attack Map Node Types

Updates the CHECK constraint on attack_map_nodes.node_type to support
the new node types: recon, tactic, exploit, connector (replacing
action, condition, infrastructure, and, or).

SQLite doesn't support ALTER TABLE to modify constraints, so we
recreate the table.

Created: 2026-02-21
"""


def upgrade(db):
    """Apply node type migration."""
    cursor = db.cursor()

    print("  → Updating attack_map_nodes node_type constraint")

    # SQLite requires table recreation to change CHECK constraints
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_map_nodes_new (
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
            CHECK (node_type IN ('recon', 'tactic', 'exploit', 'connector', 'evidence_ref', 'finding_ref', 'host_ref',
                                 'action', 'condition', 'infrastructure', 'and', 'or'))
        )
    ''')

    # Copy existing data (map old types to new ones)
    cursor.execute('''
        INSERT INTO attack_map_nodes_new
            (id, map_id, node_type, x, y, width, height, label, properties, ref_id, ref_type, created_at)
        SELECT
            id, map_id,
            CASE node_type
                WHEN 'action' THEN 'recon'
                WHEN 'condition' THEN 'tactic'
                WHEN 'infrastructure' THEN 'exploit'
                WHEN 'and' THEN 'connector'
                WHEN 'or' THEN 'connector'
                ELSE node_type
            END,
            x, y, width, height, label, properties, ref_id, ref_type, created_at
        FROM attack_map_nodes
    ''')

    cursor.execute('DROP TABLE attack_map_nodes')
    cursor.execute('ALTER TABLE attack_map_nodes_new RENAME TO attack_map_nodes')

    # Recreate indexes
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attack_map_nodes_map
        ON attack_map_nodes(map_id)
    ''')

    db.commit()
    print("  ✓ Attack map node types updated")


def downgrade(db):
    """Rollback node type migration."""
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attack_map_nodes_old (
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

    cursor.execute('''
        INSERT INTO attack_map_nodes_old
            (id, map_id, node_type, x, y, width, height, label, properties, ref_id, ref_type, created_at)
        SELECT
            id, map_id,
            CASE node_type
                WHEN 'recon' THEN 'action'
                WHEN 'tactic' THEN 'condition'
                WHEN 'exploit' THEN 'infrastructure'
                WHEN 'connector' THEN 'and'
                ELSE node_type
            END,
            x, y, width, height, label, properties, ref_id, ref_type, created_at
        FROM attack_map_nodes
    ''')

    cursor.execute('DROP TABLE attack_map_nodes')
    cursor.execute('ALTER TABLE attack_map_nodes_old RENAME TO attack_map_nodes')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_attack_map_nodes_map
        ON attack_map_nodes(map_id)
    ''')

    db.commit()
    print("  ✓ Rolled back node type changes")

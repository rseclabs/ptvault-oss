"""
Migration 007: Add Test Plans Tables

Adds tables for MITRE ATT&CK and Atomic Red Team integration:
- atomics: Atomic Red Team test library
- atomics_metadata: Library version tracking
- test_plans: Test plan templates
- test_plan_items: Individual tests within plans
- navigator_layers: MITRE ATT&CK Navigator layers
- test_executions: Engagement-specific test tracking

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Migration: Add atomics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS atomics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technique_id TEXT NOT NULL,
            technique_name TEXT NOT NULL,
            tactic TEXT,
            atomic_test_index INTEGER NOT NULL,
            atomic_test_name TEXT NOT NULL,
            description TEXT,
            supported_platforms TEXT,
            executor_name TEXT,
            executor_command TEXT,
            executor_cleanup TEXT,
            input_arguments TEXT,
            dependencies TEXT,
            elevation_required INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(technique_id, atomic_test_index)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_atomics_technique ON atomics(technique_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_atomics_tactic ON atomics(tactic)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_atomics_executor ON atomics(executor_name)')

    # Migration: Add atomics_metadata table (singleton)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS atomics_metadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version TEXT,
            last_updated TIMESTAMP,
            total_techniques INTEGER DEFAULT 0,
            total_tests INTEGER DEFAULT 0,
            download_path TEXT
        )
    ''')

    # Migration: Add test_plans table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            target_platform TEXT DEFAULT 'all',
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_plans_platform ON test_plans(target_platform)')

    # Migration: Add test_plan_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_plan_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_plan_id INTEGER NOT NULL,
            atomic_id INTEGER,
            custom_name TEXT,
            custom_command TEXT,
            custom_platform TEXT,
            sort_order INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            input_overrides TEXT,
            notes TEXT,
            technique_id TEXT,
            atomic_test_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_plan_id) REFERENCES test_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (atomic_id) REFERENCES atomics(id) ON DELETE SET NULL
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_plan_items_plan ON test_plan_items(test_plan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_plan_items_atomic ON test_plan_items(atomic_id)')

    # Migration: Add navigator_layers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS navigator_layers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            domain TEXT DEFAULT 'enterprise-attack',
            layer_json TEXT NOT NULL,
            technique_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_navigator_layers_domain ON navigator_layers(domain)')

    # Migration: Add test_executions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            test_plan_id INTEGER NOT NULL,
            test_plan_item_id INTEGER NOT NULL,
            host_id INTEGER,
            status TEXT DEFAULT 'pending',
            execution_started_at TIMESTAMP,
            execution_completed_at TIMESTAMP,
            execution_output TEXT,
            execution_notes TEXT,
            evidence_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
            FOREIGN KEY (test_plan_id) REFERENCES test_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (test_plan_item_id) REFERENCES test_plan_items(id) ON DELETE CASCADE,
            FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE SET NULL,
            FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE SET NULL
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_executions_engagement ON test_executions(engagement_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_executions_plan ON test_executions(test_plan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_test_executions_status ON test_executions(status)')

    db.commit()
    print("  ✓ Test plans tables created")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    # Drop indexes
    cursor.execute('DROP INDEX IF EXISTS idx_test_executions_status')
    cursor.execute('DROP INDEX IF EXISTS idx_test_executions_plan')
    cursor.execute('DROP INDEX IF EXISTS idx_test_executions_engagement')
    cursor.execute('DROP INDEX IF EXISTS idx_navigator_layers_domain')
    cursor.execute('DROP INDEX IF EXISTS idx_test_plan_items_atomic')
    cursor.execute('DROP INDEX IF EXISTS idx_test_plan_items_plan')
    cursor.execute('DROP INDEX IF EXISTS idx_test_plans_platform')
    cursor.execute('DROP INDEX IF EXISTS idx_atomics_executor')
    cursor.execute('DROP INDEX IF EXISTS idx_atomics_tactic')
    cursor.execute('DROP INDEX IF EXISTS idx_atomics_technique')

    # Drop tables
    cursor.execute('DROP TABLE IF EXISTS test_executions')
    cursor.execute('DROP TABLE IF EXISTS navigator_layers')
    cursor.execute('DROP TABLE IF EXISTS test_plan_items')
    cursor.execute('DROP TABLE IF EXISTS test_plans')
    cursor.execute('DROP TABLE IF EXISTS atomics_metadata')
    cursor.execute('DROP TABLE IF EXISTS atomics')

    db.commit()
    print("  ✓ Test plans tables removed")

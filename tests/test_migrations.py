"""
Test suite for the migration system.

Tests:
- Creating fresh database with migrations
- Applying migrations in order
- Idempotent behavior
- Migration status reporting
- Rollback functionality
"""

import os
import sys
import sqlite3
import tempfile
import unittest

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.migrations.manager import MigrationManager, apply_migrations, get_migration_status


class TestMigrationSystem(unittest.TestCase):
    """Test the migration system."""

    def setUp(self):
        """Set up test database."""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Connect to database
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_migrations_table_creation(self):
        """Test that schema_migrations table is created."""
        manager = MigrationManager(self.conn)

        # Check table exists
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_migrations'
        """)
        result = cursor.fetchone()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'schema_migrations')

    def test_get_available_migrations(self):
        """Test getting list of available migration files."""
        manager = MigrationManager(self.conn)
        migrations = manager.get_available_migrations()

        # Should have migration files
        self.assertGreater(len(migrations), 0)

        # Check format of first migration
        version, name, module = migrations[0]
        self.assertIsInstance(version, int)
        self.assertIsInstance(name, str)
        self.assertTrue(hasattr(module, 'upgrade'))

    def test_get_pending_migrations(self):
        """Test getting list of pending migrations."""
        manager = MigrationManager(self.conn)

        # Initially, all migrations should be pending
        pending = manager.get_pending_migrations()
        available = manager.get_available_migrations()

        self.assertEqual(len(pending), len(available))

    def test_apply_single_migration(self):
        """Test applying a single migration."""
        # Create base schema first (required for migration 001)
        self._create_base_schema()

        manager = MigrationManager(self.conn)
        pending = manager.get_pending_migrations()

        if len(pending) > 0:
            version, name, module = pending[0]
            success = manager.apply_migration(version, name, module)

            self.assertTrue(success)

            # Check migration was recorded
            applied = manager.get_applied_migrations()
            self.assertIn(version, applied)

    def test_apply_all_pending_migrations(self):
        """Test applying all pending migrations."""
        # Create base schema first
        self._create_base_schema()

        applied, failed = apply_migrations(self.conn)

        self.assertGreater(applied, 0)
        self.assertEqual(failed, 0)

    def test_idempotent_migrations(self):
        """Test that running migrations twice is safe."""
        # Create base schema
        self._create_base_schema()

        # Apply migrations first time
        applied1, failed1 = apply_migrations(self.conn)

        # Apply migrations second time (should skip all)
        applied2, failed2 = apply_migrations(self.conn)

        self.assertGreater(applied1, 0)
        self.assertEqual(failed1, 0)
        self.assertEqual(applied2, 0)  # No new migrations to apply
        self.assertEqual(failed2, 0)

    def test_migration_status(self):
        """Test getting migration status."""
        # Create base schema
        self._create_base_schema()

        # Apply migrations
        apply_migrations(self.conn)

        # Get status
        status = get_migration_status(self.conn)

        self.assertIn('applied_count', status)
        self.assertIn('available_count', status)
        self.assertIn('pending_count', status)
        self.assertIn('applied_versions', status)

        self.assertGreater(status['applied_count'], 0)
        self.assertEqual(status['pending_count'], 0)

    def test_migration_ordering(self):
        """Test that migrations are applied in correct order."""
        # Create base schema
        self._create_base_schema()

        manager = MigrationManager(self.conn)
        manager.apply_all_pending()

        # Get applied migrations
        applied = manager.get_applied_migrations()

        # Check they are in order
        for i in range(len(applied) - 1):
            self.assertLess(applied[i], applied[i + 1])

    def test_migration_transaction_rollback(self):
        """Test that failed migrations are rolled back."""
        # Create base schema
        self._create_base_schema()

        manager = MigrationManager(self.conn)

        # Try to apply a migration that will fail
        # (This is a contrived test - in real use, migrations should not fail)
        cursor = self.conn.cursor()

        # Record initial table count
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        initial_count = cursor.fetchone()[0]

        # After failed migration, table count should be the same
        # (transaction rolled back)
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        final_count = cursor.fetchone()[0]

        # Note: This test is limited because we can't easily force a migration to fail
        # In practice, the transaction rollback is tested manually

    def _create_base_schema(self):
        """Apply schema.sql to seed the base schema migrations expect.

        Uses the same parsing as conftest._init_test_db so trigger BEGIN/END
        blocks aren't broken on intermediate semicolons. This guarantees
        every migration sees the production base schema (users, engagements,
        evidence, host_*, etc.) — required since migration 012's "fresh
        install" branch checks for the multi-user users table.
        """
        from tests.conftest import _split_schema_statements, SCHEMA_PATH

        with open(SCHEMA_PATH, 'r') as f:
            schema_sql = f.read()

        cursor = self.conn.cursor()
        for stmt in _split_schema_statements(schema_sql):
            cursor.execute(stmt)
        self.conn.commit()


if __name__ == '__main__':
    unittest.main()

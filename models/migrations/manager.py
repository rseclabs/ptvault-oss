"""
Migration Manager for PTVault

Provides versioned database migrations with tracking and rollback support.
"""

import os
import importlib.util
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Manages database migrations with version tracking.

    Features:
    - Sequential migration execution
    - Version tracking in schema_migrations table
    - Idempotent (safe to run multiple times)
    - Transaction-wrapped for safety
    - Detailed logging
    """

    def __init__(self, db):
        """
        Initialize migration manager.

        Args:
            db: SQLite database connection
        """
        self.db = db
        self.cursor = db.cursor()
        from config import BASE_DIR
        self.migrations_dir = os.path.join(
            BASE_DIR, 'models', 'migrations', 'versions'
        )

        # Ensure migrations directory exists
        if not os.path.exists(self.migrations_dir):
            os.makedirs(self.migrations_dir)

        # Ensure schema_migrations table exists
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        """Create schema_migrations table if it doesn't exist."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db.commit()
        logger.info("Schema migrations table ready")

    def get_applied_migrations(self) -> List[int]:
        """
        Get list of applied migration versions.

        Returns:
            List of version numbers that have been applied
        """
        self.cursor.execute('SELECT version FROM schema_migrations ORDER BY version')
        return [row[0] for row in self.cursor.fetchall()]

    def get_available_migrations(self) -> List[Tuple[int, str, object]]:
        """
        Get list of available migration files.

        Returns:
            List of tuples: (version, name, module)
        """
        migrations = []

        if not os.path.exists(self.migrations_dir):
            return migrations

        for filename in os.listdir(self.migrations_dir):
            if not filename.endswith('.py') or filename.startswith('__'):
                continue

            # Parse filename: 001_add_feature.py
            try:
                version_str = filename.split('_')[0]
                version = int(version_str)
                name = filename[len(version_str)+1:-3]  # Remove version_ and .py

                # Load the migration module
                filepath = os.path.join(self.migrations_dir, filename)
                spec = importlib.util.spec_from_file_location(
                    f"migration_{version}",
                    filepath
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                migrations.append((version, name, module))
            except (ValueError, IndexError, AttributeError) as e:
                logger.warning(f"Skipping invalid migration file {filename}: {e}")
                continue

        # Sort by version
        migrations.sort(key=lambda x: x[0])
        return migrations

    def get_pending_migrations(self) -> List[Tuple[int, str, object]]:
        """
        Get migrations that haven't been applied yet.

        Returns:
            List of tuples: (version, name, module)
        """
        applied = set(self.get_applied_migrations())
        available = self.get_available_migrations()

        return [
            (version, name, module)
            for version, name, module in available
            if version not in applied
        ]

    def apply_migration(self, version: int, name: str, module) -> bool:
        """
        Apply a single migration.

        Args:
            version: Migration version number
            name: Migration name
            module: Migration module with upgrade() function

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Applying migration {version:03d}: {name}")

            # Begin transaction
            self.db.execute('BEGIN TRANSACTION')

            try:
                # Execute the upgrade function
                if not hasattr(module, 'upgrade'):
                    raise AttributeError(f"Migration {version} has no upgrade() function")

                module.upgrade(self.db)

                # Record migration in schema_migrations
                self.cursor.execute('''
                    INSERT INTO schema_migrations (version, name)
                    VALUES (?, ?)
                ''', (version, name))

                # Commit transaction
                self.db.commit()

                logger.info(f"✓ Migration {version:03d} applied successfully")
                return True

            except Exception as e:
                # Rollback on error
                self.db.rollback()
                logger.error(f"✗ Migration {version:03d} failed: {e}")
                raise

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False

    def apply_all_pending(self) -> Tuple[int, int]:
        """
        Apply all pending migrations.

        Returns:
            Tuple of (applied_count, failed_count)
        """
        pending = self.get_pending_migrations()

        if not pending:
            logger.info("No pending migrations")
            return (0, 0)

        logger.info(f"Found {len(pending)} pending migration(s)")

        applied_count = 0
        failed_count = 0

        for version, name, module in pending:
            if self.apply_migration(version, name, module):
                applied_count += 1
            else:
                failed_count += 1
                # Stop on first failure
                break

        return (applied_count, failed_count)

    def rollback_migration(self, version: int) -> bool:
        """
        Rollback a specific migration (if downgrade is available).

        Args:
            version: Migration version to rollback

        Returns:
            True if successful, False otherwise
        """
        # Find the migration module
        available = self.get_available_migrations()
        migration = None

        for v, name, module in available:
            if v == version:
                migration = (v, name, module)
                break

        if not migration:
            logger.error(f"Migration {version} not found")
            return False

        v, name, module = migration

        # Check if downgrade function exists
        if not hasattr(module, 'downgrade'):
            logger.warning(f"Migration {version} has no downgrade() function")
            return False

        try:
            logger.info(f"Rolling back migration {version:03d}: {name}")

            # Begin transaction
            self.db.execute('BEGIN TRANSACTION')

            try:
                # Execute the downgrade function
                module.downgrade(self.db)

                # Remove from schema_migrations
                self.cursor.execute('''
                    DELETE FROM schema_migrations WHERE version = ?
                ''', (version,))

                # Commit transaction
                self.db.commit()

                logger.info(f"✓ Migration {version:03d} rolled back successfully")
                return True

            except Exception as e:
                # Rollback on error
                self.db.rollback()
                logger.error(f"✗ Rollback of migration {version:03d} failed: {e}")
                raise

        except Exception as e:
            logger.error(f"Failed to rollback migration {version}: {e}")
            return False

    def get_status(self) -> Dict:
        """
        Get migration status information.

        Returns:
            Dictionary with migration status details
        """
        applied = self.get_applied_migrations()
        available = self.get_available_migrations()
        pending = self.get_pending_migrations()

        return {
            'applied_count': len(applied),
            'available_count': len(available),
            'pending_count': len(pending),
            'applied_versions': applied,
            'pending_migrations': [
                {'version': v, 'name': n}
                for v, n, _ in pending
            ]
        }


def apply_migrations(db) -> Tuple[int, int]:
    """
    Convenience function to apply all pending migrations.

    Args:
        db: SQLite database connection

    Returns:
        Tuple of (applied_count, failed_count)
    """
    manager = MigrationManager(db)
    return manager.apply_all_pending()


def get_migration_status(db) -> Dict:
    """
    Convenience function to get migration status.

    Args:
        db: SQLite database connection

    Returns:
        Dictionary with migration status details
    """
    manager = MigrationManager(db)
    return manager.get_status()


def rollback_last_migration(db) -> bool:
    """
    Convenience function to rollback the most recent migration.

    Args:
        db: SQLite database connection

    Returns:
        True if successful, False otherwise
    """
    manager = MigrationManager(db)
    applied = manager.get_applied_migrations()

    if not applied:
        logger.info("No migrations to rollback")
        return False

    last_version = applied[-1]
    return manager.rollback_migration(last_version)

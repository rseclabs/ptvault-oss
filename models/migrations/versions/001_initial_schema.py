"""
Migration 001: Initial Schema

Creates the base PTVault schema from schema.sql.
This migration is automatically applied when initializing a new database.

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the initial schema migration."""
    cursor = db.cursor()

    # Note: Initial schema is applied by init_db() from schema.sql
    # This migration exists for tracking purposes only
    # If tables don't exist, they will be created by schema.sql

    # Verify FTS table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_fts'")
    if not cursor.fetchone():
        raise Exception("Initial schema not applied - run init_db() first")

    print("  ✓ Initial schema verified")


def downgrade(db):
    """
    Rollback not supported for initial schema.

    The initial schema cannot be rolled back as it would destroy the entire database.
    """
    raise NotImplementedError("Cannot rollback initial schema")

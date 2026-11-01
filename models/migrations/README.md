# PTVault Migration System

A robust, versioned database migration system for PTVault.

## Quick Start

### Check Migration Status

```bash
python migrate.py status
```

### Apply Pending Migrations

```bash
python migrate.py apply
```

### List All Migrations

```bash
python migrate.py list
```

### Rollback Last Migration

```bash
python migrate.py rollback
```

## Directory Structure

```
models/migrations/
├── __init__.py           # Package exports
├── manager.py            # MigrationManager class
├── README.md             # This file
└── versions/             # Migration files
    ├── 001_initial_schema.py
    ├── 002_add_host_sub_tables.py
    ├── 003_add_host_indicators.py
    ├── 004_add_commands_table.py
    ├── 005_add_shell_oneliners_table.py
    ├── 006_add_reporting_tables.py
    ├── 007_add_testplans_tables.py
    ├── 008_add_saved_filters_table.py
    └── 009_add_composite_indexes.py
```

## Creating a New Migration

1. **Create the migration file:**

```bash
# Determine next version number
ls -1 models/migrations/versions/*.py | tail -1
# 009_add_composite_indexes.py

# Create new migration
touch models/migrations/versions/010_my_new_feature.py
```

2. **Write the migration:**

```python
"""
Migration 010: My New Feature

Add description of what this migration does.

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Add your schema changes here
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS my_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.commit()
    print("  ✓ My table created")


def downgrade(db):
    """Rollback the migration (optional)."""
    cursor = db.cursor()

    cursor.execute('DROP TABLE IF EXISTS my_table')

    db.commit()
    print("  ✓ My table removed")
```

3. **Test the migration:**

```bash
# Check status
python migrate.py status

# Apply the migration
python migrate.py apply

# Verify
python migrate.py list
```

## Migration Best Practices

### DO

- Use sequential numbering (001, 002, 003)
- Add descriptive names
- Include docstrings explaining what and why
- Use `IF NOT EXISTS` for idempotency
- Test on both fresh and existing databases
- Add indexes for foreign keys
- Commit at the end of upgrade()

### DON'T

- Skip version numbers
- Modify existing migrations after they've been applied
- Use string formatting for SQL (use parameterized queries)
- Forget to handle NULL defaults for new columns
- Break migration dependencies

## How It Works

1. **Version Tracking**: The `schema_migrations` table tracks which migrations have been applied

2. **Sequential Execution**: Migrations are applied in numeric order

3. **Transaction Safety**: Each migration runs in a transaction and rolls back on error

4. **Idempotency**: Migrations use `IF NOT EXISTS` and check for existing columns

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  PTVault Application                 │
│  app.py calls run_migrations() on startup           │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              MigrationManager                        │
│  - Loads migration files from versions/             │
│  - Checks schema_migrations table                   │
│  - Applies pending migrations in order              │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│            schema_migrations Table                   │
│  id | version | name            | applied_at        │
│  ───┼─────────┼─────────────────┼──────────────────│
│  1  | 1       | initial_schema  | 2026-02-09 10:00 │
│  2  | 2       | add_host_tables | 2026-02-09 10:00 │
│  3  | 3       | host_indicators | 2026-02-09 10:00 │
└─────────────────────────────────────────────────────┘
```

## API Reference

### Python API

```python
from models.database import get_db_connection
from models.migrations import (
    apply_migrations,
    get_migration_status,
    rollback_last_migration,
    MigrationManager
)

# Apply all pending migrations
conn = get_db_connection()
applied, failed = apply_migrations(conn)
conn.close()

# Get migration status
conn = get_db_connection()
status = get_migration_status(conn)
print(f"Applied: {status['applied_count']}")
print(f"Pending: {status['pending_count']}")
conn.close()

# Rollback last migration
conn = get_db_connection()
success = rollback_last_migration(conn)
conn.close()

# Advanced usage with MigrationManager
conn = get_db_connection()
manager = MigrationManager(conn)
pending = manager.get_pending_migrations()
for version, name, module in pending:
    print(f"{version}: {name}")
conn.close()
```

### CLI

```bash
# Show migration status
python migrate.py status

# List all migrations
python migrate.py list

# Apply pending migrations
python migrate.py apply

# Rollback last migration
python migrate.py rollback

# Rollback specific migration
python migrate.py rollback --version 5
```

## Troubleshooting

### Migration Failed

**Check the logs for error details:**

```bash
python migrate.py apply
```

**Common issues:**
- Missing table/column dependencies
- Syntax error in SQL
- Database locked
- Schema conflicts

### View Applied Migrations

```bash
sqlite3 data/ptvault.db "SELECT * FROM schema_migrations ORDER BY version"
```

### Manually Mark Migration as Applied

```bash
# Only do this if you've manually applied the schema changes
sqlite3 data/ptvault.db "INSERT INTO schema_migrations (version, name) VALUES (10, 'my_migration')"
```

### Reset Migrations (Development Only)

```bash
# WARNING: This deletes all data!
rm data/ptvault.db
python -c "from models.database import init_db; init_db()"
```

## Testing

Run the migration test suite:

```bash
python tests/test_migrations.py
```

Tests include:
- Creating migrations table
- Getting available/pending migrations
- Applying single migration
- Applying all pending migrations
- Idempotent behavior (running twice)
- Migration status reporting
- Transaction rollback on error

## Support

For detailed documentation, see [`docs/MIGRATIONS.md`](../../docs/MIGRATIONS.md)

For migration issues:
1. Check the troubleshooting section
2. Review the migration file for comments
3. Run the test suite
4. Check application logs

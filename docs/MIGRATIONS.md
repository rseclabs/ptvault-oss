# PTVault Database Migrations

## Overview

PTVault uses a versioned migration system to manage database schema changes. This system provides:

- Sequential, numbered migrations
- Version tracking in `schema_migrations` table
- Idempotent behavior (safe to run multiple times)
- Transaction-wrapped migrations for safety
- Optional rollback support

## Architecture

```
models/migrations/
├── __init__.py           # Package exports
├── manager.py            # MigrationManager class
└── versions/             # Migration files
    ├── 001_initial_schema.py
    ├── 002_add_host_sub_tables.py
    ├── 003_add_host_indicators.py
    └── ...
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `MigrationManager` | Manages migration execution and tracking |
| `schema_migrations` table | Tracks which migrations have been applied |
| `versions/` directory | Contains numbered migration files |
| `upgrade()` function | Applies a migration |
| `downgrade()` function | Rolls back a migration (optional) |

## Creating a New Migration

### Step 1: Create Migration File

Create a new file in `models/migrations/versions/` with the next sequential number:

```bash
# Find the highest existing migration number
ls -1 models/migrations/versions/*.py | tail -1
# 009_add_composite_indexes.py

# Create new migration 010
touch models/migrations/versions/010_add_new_feature.py
```

### Step 2: Write Migration Code

```python
"""
Migration 010: Add New Feature

Description of what this migration does and why.

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Add your schema changes here
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS new_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_new_table_name ON new_table(name)')

    db.commit()
    print("  ✓ New table created")


def downgrade(db):
    """Rollback the migration (optional)."""
    cursor = db.cursor()

    cursor.execute('DROP INDEX IF EXISTS idx_new_table_name')
    cursor.execute('DROP TABLE IF EXISTS new_table')

    db.commit()
    print("  ✓ New table removed")
```

### Step 3: Test the Migration

```bash
# Run the test suite
python -m pytest tests/test_migrations.py -v

# Or test manually
python -c "
from models.database import get_db_connection
from models.migrations import apply_migrations

conn = get_db_connection()
applied, failed = apply_migrations(conn)
print(f'Applied: {applied}, Failed: {failed}')
conn.close()
"
```

## Migration Best Practices

### DO

- **Use sequential numbering**: 001, 002, 003, etc.
- **Add descriptive names**: `001_initial_schema.py`, not `001.py`
- **Include docstrings**: Explain what and why
- **Use IF NOT EXISTS**: Make migrations idempotent
- **Handle NULL defaults**: For existing rows when adding columns
- **Test both ways**: Fresh database and existing database
- **Commit at the end**: Use `db.commit()` after all changes

### DON'T

- **Don't skip numbers**: Migrations must be sequential
- **Don't modify existing migrations**: Once applied, they should not change
- **Don't use string formatting**: Use parameterized queries for data
- **Don't forget indexes**: Add indexes for foreign keys and frequently queried columns
- **Don't break dependencies**: Ensure migrations can be applied in order

## Common Migration Patterns

### Adding a Table

```python
def upgrade(db):
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS new_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES parent_table(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_new_table_parent ON new_table(parent_id)')

    db.commit()
```

### Adding a Column

```python
def upgrade(db):
    cursor = db.cursor()

    # Check if column already exists
    cursor.execute("SELECT name FROM pragma_table_info('table_name')")
    existing_columns = {row[0] for row in cursor.fetchall()}

    if 'new_column' not in existing_columns:
        cursor.execute('ALTER TABLE table_name ADD COLUMN new_column TEXT DEFAULT NULL')
        print("  ✓ Added new_column to table_name")
    else:
        print("  ✓ Column new_column already exists")

    db.commit()
```

### Adding an Index

```python
def upgrade(db):
    cursor = db.cursor()

    # Composite index for common query pattern
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_table_composite
        ON table_name(column1, column2 DESC)
    ''')

    db.commit()
```

### Data Migration

```python
def upgrade(db):
    cursor = db.cursor()

    # Update existing rows
    cursor.execute('''
        UPDATE table_name
        SET new_column = COALESCE(old_column, 'default_value')
        WHERE new_column IS NULL
    ''')

    db.commit()
    print(f"  ✓ Updated {cursor.rowcount} rows")
```

## Running Migrations

### Automatic (Recommended)

Migrations run automatically when the application starts:

```python
# In app.py
if not os.path.exists(Config.DATABASE_PATH):
    init_db()
else:
    run_migrations()
```

### Manual

```python
from models.database import get_db_connection
from models.migrations import apply_migrations, get_migration_status

# Apply all pending migrations
conn = get_db_connection()
applied, failed = apply_migrations(conn)
print(f"Applied: {applied}, Failed: {failed}")
conn.close()

# Check migration status
conn = get_db_connection()
status = get_migration_status(conn)
print(f"Applied: {status['applied_count']}")
print(f"Pending: {status['pending_count']}")
conn.close()
```

### Command Line

```bash
# Check migration status
python -c "
from models.database import get_db_connection
from models.migrations import get_migration_status
import json

conn = get_db_connection()
status = get_migration_status(conn)
print(json.dumps(status, indent=2))
conn.close()
"

# Apply pending migrations
python -c "
from models.database import run_migrations
run_migrations()
"
```

## Rollback Migrations

### Single Migration

```python
from models.database import get_db_connection
from models.migrations import rollback_last_migration

conn = get_db_connection()
success = rollback_last_migration(conn)
print(f"Rollback successful: {success}")
conn.close()
```

### Notes on Rollback

- Not all migrations can be rolled back
- SQLite does not support `DROP COLUMN` in older versions
- Rollback is mainly useful during development
- Production rollbacks should be done carefully

## Troubleshooting

### Migration Failed

**Symptom:** Migration fails with an error

**Solution:**
1. Check the error message in the logs
2. Verify the migration SQL syntax
3. Check for missing dependencies (tables, columns)
4. Ensure the database is not locked
5. Rollback if possible, fix the migration, and reapply

```python
# Check which migration failed
from models.database import get_db_connection
from models.migrations import get_migration_status

conn = get_db_connection()
status = get_migration_status(conn)
print("Last applied:", status['applied_versions'][-1] if status['applied_versions'] else None)
print("Pending:", status['pending_migrations'])
conn.close()
```

### Migration Already Applied

**Symptom:** Migration appears to have run but changes are not visible

**Solution:**
1. Check `schema_migrations` table to verify the migration was recorded
2. Manually verify the schema changes
3. Check if the migration has conditional logic that may have skipped changes

```sql
-- Check applied migrations
SELECT * FROM schema_migrations ORDER BY version;

-- Check if table exists
SELECT name FROM sqlite_master WHERE type='table' AND name='table_name';

-- Check table structure
PRAGMA table_info(table_name);
```

### Migration Skipped

**Symptom:** Migration not running even though it's in the versions directory

**Solution:**
1. Check file naming (must be `NNN_name.py`)
2. Ensure `upgrade()` function exists
3. Check for syntax errors in the migration file
4. Verify the file is in the correct directory

### Database Locked

**Symptom:** `database is locked` error during migration

**Solution:**
1. Close all other connections to the database
2. Ensure no other PTVault instances are running
3. Check for stale WAL files
4. Restart the application

```bash
# Check for other processes using the database
lsof | grep ptvault.db

# Remove WAL files (only if no other processes are running)
rm data/ptvault.db-wal data/ptvault.db-shm
```

## Migration History

| Version | Name | Description |
|---------|------|-------------|
| 001 | initial_schema | Base schema from schema.sql |
| 002 | add_host_sub_tables | Host notes, ports, credentials |
| 003 | add_host_indicators | Visual indicator columns |
| 004 | add_commands_table | Custom command database |
| 005 | add_shell_oneliners_table | Shell one-liners library |
| 006 | add_reporting_tables | Writeups and reports |
| 007 | add_testplans_tables | MITRE ATT&CK and Atomic Red Team |
| 008 | add_saved_filters_table | Saved search filters |
| 009 | add_composite_indexes | Performance optimization indexes |

## API Reference

### MigrationManager

```python
from models.migrations.manager import MigrationManager

# Initialize
conn = get_db_connection()
manager = MigrationManager(conn)

# Get applied migrations
applied = manager.get_applied_migrations()

# Get available migrations
available = manager.get_available_migrations()

# Get pending migrations
pending = manager.get_pending_migrations()

# Apply all pending
applied_count, failed_count = manager.apply_all_pending()

# Get status
status = manager.get_status()

# Rollback last migration
success = manager.rollback_migration(version)
```

### Convenience Functions

```python
from models.migrations import (
    apply_migrations,
    get_migration_status,
    rollback_last_migration
)

# Apply all pending migrations
applied, failed = apply_migrations(conn)

# Get status
status = get_migration_status(conn)

# Rollback last
success = rollback_last_migration(conn)
```

## FAQs

**Q: Can I edit a migration after it's been applied?**

A: No. Once a migration has been applied to any database, it should not be modified. Create a new migration to make additional changes.

**Q: What happens if I delete a migration file?**

A: The migration system will not run it, but the `schema_migrations` table will still show it as applied. This can cause issues if the migration is needed for future migrations.

**Q: Can I reorder migrations?**

A: No. Migrations are applied in sequential order based on their version number. Reordering would require manual database manipulation.

**Q: How do I handle data migrations?**

A: Use the `upgrade()` function to update existing data. Ensure the logic handles NULL values and edge cases gracefully.

**Q: What if a migration takes a long time?**

A: Large data migrations may take time. Consider:
- Adding progress indicators
- Batching large operations
- Running migrations during maintenance windows

**Q: Can I skip a migration?**

A: Not recommended. If you must skip a migration, manually add it to `schema_migrations` table, but ensure the schema changes are not needed.

## Support

For migration issues or questions:

1. Check the troubleshooting section above
2. Review the migration file for comments
3. Check the test suite in `tests/test_migrations.py`
4. Open an issue on GitHub with migration logs

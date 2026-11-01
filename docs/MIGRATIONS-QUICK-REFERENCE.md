# PTVault Migrations - Quick Reference

## Commands

```bash
# Check status
python migrate.py status

# List all migrations
python migrate.py list

# Apply pending migrations
python migrate.py apply

# Rollback last migration
python migrate.py rollback
```

## Creating a Migration

### 1. Create File

```bash
# Find next version number
ls -1 models/migrations/versions/*.py | tail -1

# Create new migration
touch models/migrations/versions/010_my_feature.py
```

### 2. Write Migration

```python
"""
Migration 010: My Feature

Description of what this does.

Created: 2026-02-10
"""

def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Your schema changes here
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS my_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')

    db.commit()
    print("  ✓ Migration applied")

def downgrade(db):
    """Rollback (optional)."""
    cursor = db.cursor()
    cursor.execute('DROP TABLE IF EXISTS my_table')
    db.commit()
```

### 3. Apply

```bash
python migrate.py apply
```

## Common Patterns

### Add Table

```python
cursor.execute('''
    CREATE TABLE IF NOT EXISTS table_name (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES parent(id) ON DELETE CASCADE
    )
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_table_parent ON table_name(parent_id)')
```

### Add Column

```python
cursor.execute("SELECT name FROM pragma_table_info('table_name')")
existing = {row[0] for row in cursor.fetchall()}

if 'new_column' not in existing:
    cursor.execute('ALTER TABLE table_name ADD COLUMN new_column TEXT DEFAULT NULL')
```

### Add Index

```python
# Single column
cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON table(column)')

# Composite
cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON table(col1, col2 DESC)')
```

### Data Migration

```python
cursor.execute('UPDATE table SET new_col = old_col WHERE new_col IS NULL')
print(f"  - Updated {cursor.rowcount} rows")
```

## Python API

```python
from models.database import get_db_connection
from models.migrations import apply_migrations, get_migration_status

# Apply migrations
conn = get_db_connection()
applied, failed = apply_migrations(conn)
conn.close()

# Check status
conn = get_db_connection()
status = get_migration_status(conn)
print(f"Applied: {status['applied_count']}")
print(f"Pending: {status['pending_count']}")
conn.close()
```

## Database Queries

```bash
# View applied migrations
sqlite3 data/ptvault.db "SELECT * FROM schema_migrations ORDER BY version"

# Check table schema
sqlite3 data/ptvault.db ".schema table_name"

# Check table columns
sqlite3 data/ptvault.db "PRAGMA table_info(table_name)"
```

## Best Practices

- ✓ Use sequential numbering (001, 002, 003)
- ✓ Use `IF NOT EXISTS` for idempotency
- ✓ Check for existing columns before adding
- ✓ Add indexes for foreign keys
- ✓ Test on copy of production data
- ✓ Commit migrations after testing
- ✗ Don't modify applied migrations
- ✗ Don't skip version numbers
- ✗ Don't use string formatting in SQL

## Troubleshooting

### Migration Failed
```bash
# Check error output
python migrate.py apply

# Fix issue and retry
python migrate.py apply
```

### Check Migration Status
```bash
python migrate.py status
python migrate.py list
```

### Rollback if Needed
```bash
python migrate.py rollback
```

## Files

| Path | Purpose |
|------|---------|
| `models/migrations/manager.py` | Migration engine |
| `models/migrations/versions/` | Migration files |
| `migrate.py` | CLI tool |
| `docs/MIGRATIONS.md` | Full documentation |
| `docs/MIGRATION-EXAMPLE.md` | Complete example |
| `tests/test_migrations.py` | Test suite |

## Help

- Full guide: `docs/MIGRATIONS.md`
- Example walkthrough: `docs/MIGRATION-EXAMPLE.md`
- Test migrations: `python tests/test_migrations.py`

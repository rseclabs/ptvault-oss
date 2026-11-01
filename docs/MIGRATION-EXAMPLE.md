# Creating a New Migration - Example Walkthrough

This document provides a complete example of creating and applying a new migration in PTVault.

## Scenario

We want to add a new feature: **Engagement Templates**. This will allow users to create reusable engagement templates with predefined settings.

## Step 1: Plan the Schema

We need to add a new table `engagement_templates`:

```sql
CREATE TABLE engagement_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    default_status TEXT DEFAULT 'active',
    default_tags TEXT,
    template_config TEXT,  -- JSON configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

We also want to track which engagements were created from templates:

```sql
ALTER TABLE engagements
ADD COLUMN template_id INTEGER REFERENCES engagement_templates(id);
```

## Step 2: Create the Migration File

First, check the current highest migration number:

```bash
ls -1 models/migrations/versions/*.py | tail -1
# Output: models/migrations/versions/009_add_composite_indexes.py
```

Create the new migration file:

```bash
touch models/migrations/versions/010_add_engagement_templates.py
```

## Step 3: Write the Migration

Edit `models/migrations/versions/010_add_engagement_templates.py`:

```python
"""
Migration 010: Add Engagement Templates

Adds engagement templates feature to allow users to create reusable
engagement configurations.

Tables added:
- engagement_templates: Template definitions

Columns added:
- engagements.template_id: Link to template used

Created: 2026-02-10
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Create engagement_templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            default_status TEXT DEFAULT 'active',
            default_tags TEXT,
            template_config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add index on name for searching
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_engagement_templates_name
        ON engagement_templates(name)
    ''')

    # Add template_id column to engagements table
    # Check if column already exists to make migration idempotent
    cursor.execute("SELECT name FROM pragma_table_info('engagements')")
    existing_columns = {row[0] for row in cursor.fetchall()}

    if 'template_id' not in existing_columns:
        cursor.execute('''
            ALTER TABLE engagements
            ADD COLUMN template_id INTEGER
            REFERENCES engagement_templates(id)
        ''')
        print("  - Added template_id column to engagements")

    # Add index on template_id for queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_engagements_template
        ON engagements(template_id)
    ''')

    db.commit()
    print("  ✓ Engagement templates table and columns created")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    # Drop indexes
    cursor.execute('DROP INDEX IF EXISTS idx_engagements_template')
    cursor.execute('DROP INDEX IF EXISTS idx_engagement_templates_name')

    # Drop table
    cursor.execute('DROP TABLE IF EXISTS engagement_templates')

    # Note: SQLite doesn't support DROP COLUMN easily
    # In production, you'd need to recreate the engagements table
    # without the template_id column. For now, we'll leave it.
    print("  ! Cannot drop template_id column (SQLite limitation)")
    print("  ! Column will remain but be unused after rollback")

    db.commit()
    print("  ✓ Engagement templates table removed")
```

## Step 4: Test the Migration

### Option 1: Use the CLI

```bash
# Check current status
python migrate.py status

# Output:
# Migration Status
# ============================================================
# Applied:   9
# Available: 10
# Pending:   1
#
# Pending Migrations:
#   - 010: add_engagement_templates
# ============================================================

# Apply the migration
python migrate.py apply

# Output:
# Applying migrations...
# Applying migration 010: add_engagement_templates
#   - Added template_id column to engagements
#   ✓ Engagement templates table and columns created
# ✓ Migration 010 applied successfully
#
# ✓ Applied 1 migration(s)

# Verify
python migrate.py list

# Output:
# Migrations
# ================================================================================
# Version    Status       Name
# --------------------------------------------------------------------------------
# 001        ✓ Applied    initial_schema
# ...
# 009        ✓ Applied    add_composite_indexes
# 010        ✓ Applied    add_engagement_templates
# ================================================================================
```

### Option 2: Use Python

```python
from models.database import get_db_connection
from models.migrations import apply_migrations, get_migration_status

# Check status before
conn = get_db_connection()
status = get_migration_status(conn)
print(f"Pending: {status['pending_count']}")
conn.close()

# Apply migrations
conn = get_db_connection()
applied, failed = apply_migrations(conn)
print(f"Applied: {applied}, Failed: {failed}")
conn.close()

# Check status after
conn = get_db_connection()
status = get_migration_status(conn)
print(f"Pending: {status['pending_count']}")
conn.close()
```

### Option 3: Run Tests

```bash
python tests/test_migrations.py
```

## Step 5: Verify the Migration

### Check the Database Schema

```bash
# Check if table was created
sqlite3 data/ptvault.db ".schema engagement_templates"

# Output:
# CREATE TABLE engagement_templates (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     name TEXT NOT NULL,
#     description TEXT,
#     default_status TEXT DEFAULT 'active',
#     default_tags TEXT,
#     template_config TEXT,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );
# CREATE INDEX idx_engagement_templates_name ON engagement_templates(name);

# Check if column was added
sqlite3 data/ptvault.db "PRAGMA table_info(engagements)" | grep template_id

# Output:
# 14|template_id|INTEGER|0||0

# Check migration was recorded
sqlite3 data/ptvault.db "SELECT * FROM schema_migrations WHERE version = 10"

# Output:
# 10|add_engagement_templates|2026-02-10 10:30:00
```

### Test Idempotency

Run the migration again to ensure it's idempotent:

```bash
python migrate.py apply

# Output:
# Applying migrations...
#
# ✓ No pending migrations
```

## Step 6: Use the New Table

Now you can use the new table in your application:

```python
# In routes/engagements.py

@engagements_bp.route('/api/engagement-templates', methods=['GET'])
@require_auth
def list_templates():
    """List all engagement templates."""
    cursor = g.db.cursor()

    cursor.execute('''
        SELECT id, name, description, default_status, default_tags,
               template_config, created_at
        FROM engagement_templates
        ORDER BY name
    ''')

    templates = cursor.fetchall()

    return jsonify([dict(row) for row in templates])


@engagements_bp.route('/api/engagement-templates', methods=['POST'])
@require_auth
def create_template():
    """Create a new engagement template."""
    data = request.json
    cursor = g.db.cursor()

    cursor.execute('''
        INSERT INTO engagement_templates
        (name, description, default_status, default_tags, template_config)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data['name'],
        data.get('description'),
        data.get('default_status', 'active'),
        data.get('default_tags'),
        data.get('template_config')
    ))

    g.db.commit()

    return jsonify({
        'id': cursor.lastrowid,
        'message': 'Template created'
    }), 201
```

## Step 7: Document the Migration

Update the migration history in `docs/MIGRATIONS.md`:

```markdown
## Migration History

| Version | Name | Description |
|---------|------|-------------|
| 001 | initial_schema | Base schema from schema.sql |
| ...
| 009 | add_composite_indexes | Performance optimization indexes |
| 010 | add_engagement_templates | Engagement templates feature |
```

## Step 8: Rollback (If Needed)

If you need to rollback the migration:

```bash
python migrate.py rollback

# Output:
# Rolling back migration 010: add_engagement_templates
# ! Cannot drop template_id column (SQLite limitation)
# ! Column will remain but be unused after rollback
# ✓ Engagement templates table removed
#
# ✓ Rollback successful
```

## Common Patterns

### Adding a Table with Foreign Key

```python
def upgrade(db):
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS child_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES parent_table(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_child_parent ON child_table(parent_id)')

    db.commit()
```

### Adding Multiple Columns

```python
def upgrade(db):
    cursor = db.cursor()

    # Check existing columns
    cursor.execute("SELECT name FROM pragma_table_info('table_name')")
    existing_columns = {row[0] for row in cursor.fetchall()}

    columns_to_add = {
        'column1': 'TEXT DEFAULT NULL',
        'column2': 'INTEGER DEFAULT 0',
        'column3': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
    }

    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            cursor.execute(f'ALTER TABLE table_name ADD COLUMN {col_name} {col_type}')
            print(f"  - Added {col_name}")

    db.commit()
```

### Data Migration

```python
def upgrade(db):
    cursor = db.cursor()

    # Add new column
    cursor.execute('ALTER TABLE table_name ADD COLUMN new_col TEXT')

    # Migrate data from old column
    cursor.execute('''
        UPDATE table_name
        SET new_col = old_col
        WHERE new_col IS NULL
    ''')

    rows_updated = cursor.rowcount
    print(f"  - Migrated {rows_updated} rows")

    db.commit()
```

### Creating Indexes

```python
def upgrade(db):
    cursor = db.cursor()

    # Single column index
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_table_col ON table_name(column)')

    # Composite index
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_table_comp ON table_name(col1, col2 DESC)')

    # Partial index (conditional)
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_table_active
        ON table_name(column)
        WHERE status = 'active'
    ''')

    db.commit()
```

## Tips

1. **Always test on a copy of production data** before applying in production
2. **Make migrations idempotent** using `IF NOT EXISTS` and column checks
3. **Handle NULL defaults** for new columns in existing tables
4. **Add indexes** for foreign keys and frequently queried columns
5. **Use transactions** - migrations are automatically wrapped in transactions
6. **Document what and why** in the migration docstring
7. **Test rollback** if you implement the downgrade function
8. **Check migration status** before and after applying

## Troubleshooting

### Migration Fails

```bash
# Check the error in the output
python migrate.py apply

# If it failed, check the database state
sqlite3 data/ptvault.db ".schema"

# Manually fix any issues, then try again
python migrate.py apply
```

### Column Already Exists

This means the migration wasn't properly checking for existing columns. Update the migration:

```python
# Check before adding
cursor.execute("SELECT name FROM pragma_table_info('table_name')")
existing_columns = {row[0] for row in cursor.fetchall()}

if 'new_column' not in existing_columns:
    cursor.execute('ALTER TABLE table_name ADD COLUMN new_column TEXT')
```

### Table Already Exists

Use `CREATE TABLE IF NOT EXISTS`:

```python
cursor.execute('CREATE TABLE IF NOT EXISTS table_name (...)')
```

## Next Steps

After successfully creating and applying your migration:

1. Commit the migration file to git
2. Update application code to use the new tables/columns
3. Add API endpoints for the new feature
4. Update frontend to use the new endpoints
5. Add tests for the new feature
6. Document the new feature in README.md

## References

- Full Migration Guide: `docs/MIGRATIONS.md`
- Migration Manager: `models/migrations/manager.py`
- Existing Migrations: `models/migrations/versions/`
- Test Suite: `tests/test_migrations.py`

"""
Migration 010: Add Report Templates

Adds support for reusable report templates with auto-population
and multi-engagement comparison capabilities.

Created: 2026-02-09
"""


def upgrade(db):
    """Apply migration: Add report template tables."""
    cursor = db.cursor()

    # Report templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'custom',
            structure TEXT NOT NULL,
            placeholders TEXT,
            is_default INTEGER DEFAULT 0,
            is_public INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Report sections table for auto-populated sections
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS report_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            template_id INTEGER,
            section_type TEXT NOT NULL,
            title TEXT,
            content TEXT,
            config TEXT,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            FOREIGN KEY (template_id) REFERENCES report_templates(id) ON DELETE SET NULL
        )
    ''')

    # Add indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_report_templates_category
        ON report_templates(category)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_report_templates_default
        ON report_templates(is_default)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_report_sections_report
        ON report_sections(report_id, display_order)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_report_sections_template
        ON report_sections(template_id)
    ''')

    db.commit()

    print("  ✓ Created report_templates table")
    print("  ✓ Created report_sections table")
    print("  ✓ Added performance indexes")


def downgrade(db):
    """Rollback migration: Remove report template tables."""
    cursor = db.cursor()

    cursor.execute('DROP INDEX IF EXISTS idx_report_sections_template')
    cursor.execute('DROP INDEX IF EXISTS idx_report_sections_report')
    cursor.execute('DROP INDEX IF EXISTS idx_report_templates_default')
    cursor.execute('DROP INDEX IF EXISTS idx_report_templates_category')

    cursor.execute('DROP TABLE IF EXISTS report_sections')
    cursor.execute('DROP TABLE IF EXISTS report_templates')

    db.commit()

    print("  ✓ Removed report template tables")

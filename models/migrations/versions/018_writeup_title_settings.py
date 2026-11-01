"""
Migration 018: Add title display settings to writeups table.

Adds show_title_in_report and report_heading_level columns so users can
control how writeup names appear in generated reports.
"""


def upgrade(cursor):
    # Add show_title_in_report column (default True - show title)
    cursor.execute('''
        ALTER TABLE writeups ADD COLUMN show_title_in_report INTEGER DEFAULT 1
    ''')

    # Add report_heading_level column (default 'h3')
    cursor.execute('''
        ALTER TABLE writeups ADD COLUMN report_heading_level TEXT DEFAULT 'h3'
    ''')


def downgrade(cursor):
    pass  # SQLite doesn't support DROP COLUMN easily

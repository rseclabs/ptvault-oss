"""Migration 025: Independent note titles

Adds a `title` column to engagement_notes and host_notes so the note
title is stored independently from the note body content.

Existing rows are backfilled by extracting the first non-empty line from
their content (stripping leading markdown heading characters), matching
what the frontend was deriving at display time.

Created: 2026-05-15
"""


def _first_line_title(content):
    """Extract a display title from a note's content (mirrors frontend logic)."""
    if not content:
        return ''
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped:
            # Strip markdown heading prefix (# ## ### …)
            import re
            cleaned = re.sub(r'^#+\s*', '', stripped)
            return cleaned[:200]
    return ''


def upgrade(db):
    cursor = db.cursor()

    for table in ('engagement_notes', 'host_notes'):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]

        if 'title' not in columns:
            print(f"  -> Adding title column to {table}")
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN title TEXT NOT NULL DEFAULT ''"
            )

        # Backfill titles for existing rows that have empty title
        cursor.execute(f"SELECT id, content FROM {table} WHERE title = ''")
        rows = cursor.fetchall()
        print(f"  -> Backfilling {len(rows)} title(s) in {table}")
        for row in rows:
            note_id, content = row[0], row[1]
            title = _first_line_title(content)
            cursor.execute(
                f"UPDATE {table} SET title = ? WHERE id = ?",
                (title, note_id),
            )

    db.commit()
    print("  -> Note titles migration completed")


def downgrade(db):
    # SQLite cannot drop columns; nullify instead
    cursor = db.cursor()
    cursor.execute("UPDATE engagement_notes SET title = ''")
    cursor.execute("UPDATE host_notes SET title = ''")
    db.commit()

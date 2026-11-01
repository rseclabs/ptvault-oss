"""Migration 030: Rebuild evidence_fts lost by the encryption migration

Before the switch to sqlcipher_export(), converting the database to or from
SQLCipher replayed iterdump() output and skipped the INSERT INTO sqlite_master
statement that defines the evidence_fts virtual table. The FTS shadow tables
(evidence_fts_content, _segments, ...) and the three sync triggers were still
copied, so every evidence INSERT/UPDATE/DELETE then failed with
"no such table: main.evidence_fts". This happened on every fresh install,
because first-time setup encrypts the database.

Migration 021 cannot repair that state: it runs before setup encrypts the
database, and CREATE VIRTUAL TABLE fails while the orphaned shadow tables
exist. This migration drops the orphans, recreates the FTS table and its
triggers, and re-indexes all evidence.

Created: 2026-11-01
"""

SHADOW_TABLES = (
    'evidence_fts_content',
    'evidence_fts_docsize',
    'evidence_fts_segdir',
    'evidence_fts_segments',
    'evidence_fts_stat',
)


def upgrade(db):
    cursor = db.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence'"
    )
    if cursor.fetchone() is None:
        return  # evidence table not created yet; schema.sql builds FTS with it

    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE name='evidence_fts'"
    )
    row = cursor.fetchone()
    if row and row[0] and row[0].upper().startswith('CREATE VIRTUAL TABLE'):
        print("  ✓ evidence_fts present — nothing to rebuild")
        return

    print("  -> evidence_fts missing — rebuilding full-text index")
    for table in SHADOW_TABLES:
        cursor.execute(f'DROP TABLE IF EXISTS "{table}"')

    cursor.execute("""
        CREATE VIRTUAL TABLE evidence_fts USING fts4(
            title,
            content,
            metadata,
            tokenize=unicode61
        )
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS evidence_fts_insert
        AFTER INSERT ON evidence
        BEGIN
            INSERT INTO evidence_fts(docid, title, content, metadata)
            VALUES (new.id, new.title, new.content, new.metadata);
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS evidence_fts_update
        AFTER UPDATE ON evidence
        BEGIN
            UPDATE evidence_fts
            SET title = new.title,
                content = new.content,
                metadata = new.metadata
            WHERE docid = old.id;
        END
    """)
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS evidence_fts_delete
        AFTER DELETE ON evidence
        BEGIN
            DELETE FROM evidence_fts WHERE docid = old.id;
        END
    """)
    cursor.execute("""
        INSERT INTO evidence_fts(docid, title, content, metadata)
        SELECT id, title, content, metadata FROM evidence
    """)
    db.commit()
    print(f"  -> evidence_fts rebuilt ({cursor.rowcount} evidence rows indexed)")


def downgrade(db):
    # The FTS table is part of the base schema; nothing to undo.
    pass

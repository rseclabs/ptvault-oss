"""
Migration 021: Repair evidence_fts virtual table

The evidence_fts FTS4 virtual table can go missing after an encryption
migration because sqlite3.iterdump() sometimes fails to replay the
CREATE VIRTUAL TABLE statement into SQLCipher, but the three sync
triggers (evidence_fts_insert/update/delete) are still created.

Any subsequent INSERT/UPDATE/DELETE on evidence then raises:
  OperationalError: no such table: main.evidence_fts

This migration detects that broken state and either:
  - Recreates the FTS table and repopulates it from existing evidence, or
  - Drops the broken triggers so evidence operations succeed without FTS.

Created: 2026-03-30
"""


def upgrade(db):
    """Repair missing evidence_fts table."""
    cursor = db.cursor()

    # Check whether the FTS table already exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_fts'"
    )
    fts_exists = cursor.fetchone() is not None

    if fts_exists:
        print("  ✓ evidence_fts table already present — nothing to repair")
        return

    print("  -> evidence_fts table missing — attempting repair")

    # Try to recreate the FTS virtual table
    fts_created = False
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE evidence_fts USING fts4(
                title,
                content,
                metadata,
                tokenize=unicode61
            )
        """)
        fts_created = True
        print("  -> evidence_fts table created")
    except Exception as e:
        print(f"  ! FTS4 not available ({e}); dropping broken triggers instead")

    if fts_created:
        # Recreate the three sync triggers (IF NOT EXISTS handles the case where
        # they already exist)
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

        # Repopulate FTS index from all existing evidence
        try:
            cursor.execute("""
                INSERT INTO evidence_fts(docid, title, content, metadata)
                SELECT id, title, content, metadata FROM evidence
            """)
            cursor.execute("SELECT COUNT(*) FROM evidence")
            count = cursor.fetchone()[0]
            print(f"  -> FTS index rebuilt ({count} rows)")
        except Exception as e:
            print(f"  ! FTS repopulation failed: {e}")
    else:
        # FTS4 unavailable — drop the broken triggers so evidence works
        cursor.execute("DROP TRIGGER IF EXISTS evidence_fts_insert")
        cursor.execute("DROP TRIGGER IF EXISTS evidence_fts_update")
        cursor.execute("DROP TRIGGER IF EXISTS evidence_fts_delete")
        print("  -> Broken triggers removed; evidence operations will succeed without FTS")

    db.commit()
    print("  -> evidence_fts repair migration completed")


def downgrade(db):
    """No-op: the FTS table and triggers are managed by the schema."""
    pass

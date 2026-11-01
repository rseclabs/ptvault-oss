All three SQLite skill files have been updated. Here's a summary of what changed:

**SKILL.md** (109 lines):
- Fixed FTS4 query to use `docid` instead of `rowid` (matches actual trigger setup)
- Added standalone connection pattern via `get_db_connection()`
- Added Key Concepts table with file locations
- Added DAO usage, UPSERT, and generated column patterns
- Removed outdated migration pattern referencing the old monolithic system

**references/patterns.md** (259 lines):
- Fixed FTS4 section: uses `unicode61` tokenizer (not `porter`), `docid`-based triggers (not the FTS5 `content=` pattern that was incorrectly shown before)
- Added explicit warning about FTS4 vs FTS5 — pysqlcipher3 doesn't compile FTS5
- Added Generated Columns section showing `tool_name` and `severity_level` extraction from JSON
- Added UPSERT with COALESCE pattern from actual `models/database.py`
- Added junction table pattern with `INSERT OR IGNORE`
- Fixed all anti-pattern examples with accurate codebase references
- Added FTS rebuild syntax specific to FTS4

**references/workflows.md** (315 lines):
- Replaced old monolithic `run_migrations()` pattern with the versioned `MigrationManager` system (`models/migrations/versions/NNN_description.py`)
- Added migration file template with `upgrade(db)` and `downgrade(db)`
- Added column existence check using `pragma_table_info` (not `PRAGMA table_info`)
- Added index existence check pattern from migration 009
- Added full "Adding a New Table" workflow (schema.sql + migration + DAO)
- Added "Adding FTS to a Table" 4-step workflow with backfill
- Added dynamic query builder pattern from `evidence_dao.py`
- Added migration checklist and validation loop
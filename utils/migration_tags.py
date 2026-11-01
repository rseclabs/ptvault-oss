#!/usr/bin/env python3
"""
Tag Migration Script

Migrates evidence tags from comma-separated TEXT format to junction table.
This enables 10-100x faster tag queries and autocomplete functionality.

Usage:
    python3 utils/migration_tags.py

This script:
1. Reads all evidence entries with comma-separated tags
2. Parses and normalizes tags (lowercase, trim whitespace)
3. Inserts unique tags into tags table
4. Creates evidence_tags junction entries
5. Verifies migration: count tags before/after, check no data loss
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import get_db_connection


def migrate_tags_to_junction():
    """
    Migrate comma-separated tags to junction table.

    Returns:
        dict: Migration statistics
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Read all evidence entries with tags
        cursor.execute("SELECT id, tags FROM evidence WHERE tags IS NOT NULL AND tags != ''")
        evidence_with_tags = cursor.fetchall()

        print(f"Found {len(evidence_with_tags)} evidence entries with tags")

        # Step 2: Parse and collect all unique tags
        tag_to_evidence = {}  # {tag_name: [evidence_id1, evidence_id2, ...]}
        total_tag_associations = 0

        for evidence_id, tags_str in evidence_with_tags:
            # Split comma-separated tags
            tags = [tag.strip().lower() for tag in tags_str.split(',') if tag.strip()]
            total_tag_associations += len(tags)

            for tag in tags:
                if tag not in tag_to_evidence:
                    tag_to_evidence[tag] = []
                tag_to_evidence[tag].append(evidence_id)

        unique_tags = sorted(tag_to_evidence.keys())
        print(f"Found {len(unique_tags)} unique tags")
        print(f"Total tag associations: {total_tag_associations}")

        # Step 3: Insert unique tags into tags table
        inserted_tags = 0
        for tag_name in unique_tags:
            cursor.execute(
                "INSERT OR IGNORE INTO tags (name, created_at) VALUES (?, datetime('now'))",
                (tag_name,)
            )
            if cursor.rowcount > 0:
                inserted_tags += 1

        print(f"Inserted {inserted_tags} new tags into tags table")

        # Step 4: Create evidence_tags junction entries
        # First, get tag_id for each tag name
        cursor.execute("SELECT id, name FROM tags")
        tag_name_to_id = {name: id for id, name in cursor.fetchall()}

        # Bulk insert junction entries
        junction_entries = []
        for tag_name, evidence_ids in tag_to_evidence.items():
            tag_id = tag_name_to_id[tag_name]
            for evidence_id in evidence_ids:
                junction_entries.append((evidence_id, tag_id))

        cursor.executemany(
            "INSERT OR IGNORE INTO evidence_tags (evidence_id, tag_id) VALUES (?, ?)",
            junction_entries
        )

        print(f"Inserted {len(junction_entries)} junction table entries")

        # Step 5: Verify migration
        cursor.execute("SELECT COUNT(*) FROM tags")
        final_tag_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM evidence_tags")
        final_junction_count = cursor.fetchone()[0]

        print("\n=== Migration Verification ===")
        print(f"Expected unique tags: {len(unique_tags)}")
        print(f"Actual tags in table: {final_tag_count}")
        print(f"Expected tag associations: {total_tag_associations}")
        print(f"Actual junction entries: {final_junction_count}")

        # Verify counts match
        verification_passed = (
            final_tag_count >= len(unique_tags) and
            final_junction_count == total_tag_associations
        )

        if verification_passed:
            print("\n✓ Migration verification PASSED")
            print("All tags successfully migrated to junction table")
            conn.commit()

            # Note: We keep the evidence.tags column for now as backup
            # It can be manually dropped later with: ALTER TABLE evidence DROP COLUMN tags
            print("\nNote: evidence.tags column preserved for backup")
            print("Can be dropped later if verification is successful")

            return {
                'success': True,
                'evidence_count': len(evidence_with_tags),
                'unique_tags': len(unique_tags),
                'tag_associations': total_tag_associations,
                'final_tag_count': final_tag_count,
                'final_junction_count': final_junction_count
            }
        else:
            print("\n✗ Migration verification FAILED")
            print("Rolling back transaction")
            conn.rollback()
            return {
                'success': False,
                'error': 'Count mismatch after migration'
            }

    except Exception as e:
        print(f"\n✗ Migration failed with error: {e}")
        conn.rollback()
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        conn.close()


if __name__ == '__main__':
    print("Starting tag migration from comma-separated to junction table...")
    print("=" * 60)

    result = migrate_tags_to_junction()

    print("\n" + "=" * 60)
    if result['success']:
        print("Migration completed successfully!")
        sys.exit(0)
    else:
        print(f"Migration failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

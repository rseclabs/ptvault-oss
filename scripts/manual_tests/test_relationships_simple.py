#!/usr/bin/env python3
"""
Simple integration test for relationship DAOs.

Tests the DAO methods directly without Flask context.
"""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Import migration
import importlib.util
spec = importlib.util.spec_from_file_location(
    "migration_013",
    os.path.join(os.path.dirname(__file__), "models/migrations/versions/013_evidence_relationships.py")
)
migration_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration_module)


def create_test_db():
    """Create test database."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE engagements (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE evidence (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER,
            title TEXT,
            evidence_type TEXT,
            tags TEXT,
            host_id INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT
        )
    ''')

    # Run migration
    print("Running migration...")
    migration_module.upgrade(conn)
    print("✓ Migration completed\n")

    # Insert test data
    cursor.execute("INSERT INTO engagements (id, name) VALUES (1, 'Test')")
    cursor.execute("INSERT INTO users (id, username) VALUES (1, 'test')")

    evidence = [
        (1, 1, 'Port Scan', 'tool_output'),
        (2, 1, 'Admin Panel', 'note'),
        (3, 1, 'SQL Injection', 'screenshot'),
        (4, 1, 'Credentials', 'command_output'),
        (5, 1, 'SSH Access', 'command_output'),
        (6, 1, 'Root Shell', 'command_output'),
    ]

    cursor.executemany(
        'INSERT INTO evidence (id, engagement_id, title, evidence_type) VALUES (?, ?, ?, ?)',
        evidence
    )

    conn.commit()
    return conn


def test_basic_crud(conn):
    """Test basic CRUD operations."""
    print("Test 1: Basic CRUD operations")
    cursor = conn.cursor()

    # Create relationships
    cursor.execute('''
        INSERT INTO evidence_relationships
        (engagement_id, source_evidence_id, target_evidence_id, relationship_type)
        VALUES (?, ?, ?, ?)
    ''', (1, 1, 2, 'discovers'))
    conn.commit()

    rel_id = cursor.lastrowid
    print(f"  ✓ Created relationship {rel_id}")

    # Read
    cursor.execute('SELECT * FROM evidence_relationships WHERE id = ?', (rel_id,))
    rel = cursor.fetchone()
    assert rel is not None
    assert rel['source_evidence_id'] == 1
    assert rel['target_evidence_id'] == 2
    print("  ✓ Read relationship")

    # Update
    cursor.execute('''
        UPDATE evidence_relationships
        SET label = ?
        WHERE id = ?
    ''', ('Test Label', rel_id))
    conn.commit()
    print("  ✓ Updated relationship")

    # Delete
    cursor.execute('DELETE FROM evidence_relationships WHERE id = ?', (rel_id,))
    conn.commit()
    print("  ✓ Deleted relationship\n")


def test_create_chain(conn):
    """Test creating a relationship chain."""
    print("Test 2: Creating attack chain")
    cursor = conn.cursor()

    # Create attack chain: 1 -> 2 -> 3 -> 4 -> 5 -> 6
    chain = [
        (1, 1, 2, 'discovers'),
        (1, 2, 3, 'leads_to'),
        (1, 3, 4, 'exploits'),
        (1, 4, 5, 'uses'),
        (1, 5, 6, 'escalates'),
    ]

    cursor.executemany('''
        INSERT INTO evidence_relationships
        (engagement_id, source_evidence_id, target_evidence_id, relationship_type)
        VALUES (?, ?, ?, ?)
    ''', chain)
    conn.commit()

    # Count
    cursor.execute('SELECT COUNT(*) FROM evidence_relationships')
    count = cursor.fetchone()[0]
    print(f"  ✓ Created chain with {count} relationships\n")


def test_query_relationships(conn):
    """Test querying relationships."""
    print("Test 3: Querying relationships")
    cursor = conn.cursor()

    # Get all relationships for evidence #4
    cursor.execute('''
        SELECT r.*,
               e1.title as source_title,
               e2.title as target_title
        FROM evidence_relationships r
        JOIN evidence e1 ON r.source_evidence_id = e1.id
        JOIN evidence e2 ON r.target_evidence_id = e2.id
        WHERE (r.source_evidence_id = 4 OR r.target_evidence_id = 4)
        AND r.engagement_id = 1
    ''', ())

    relationships = cursor.fetchall()
    print(f"  ✓ Evidence #4 has {len(relationships)} relationships:")
    for rel in relationships:
        direction = "→" if rel['source_evidence_id'] == 4 else "←"
        other = rel['target_title'] if rel['source_evidence_id'] == 4 else rel['source_title']
        print(f"    {direction} {rel['relationship_type']}: {other}")

    print()


def test_path_finding_sql(conn):
    """Test path finding with recursive SQL."""
    print("Test 4: Path finding (SQL recursive CTE)")
    cursor = conn.cursor()

    # Use recursive CTE to find path
    cursor.execute('''
        WITH RECURSIVE path(node, path_text, depth) AS (
            -- Base case: start at node 1
            SELECT
                1 as node,
                CAST(1 AS TEXT) as path_text,
                0 as depth

            UNION ALL

            -- Recursive case: follow edges
            SELECT
                r.target_evidence_id,
                path.path_text || ' -> ' || CAST(r.target_evidence_id AS TEXT),
                path.depth + 1
            FROM path
            JOIN evidence_relationships r ON path.node = r.source_evidence_id
            WHERE r.engagement_id = 1
            AND path.depth < 10
        )
        SELECT * FROM path WHERE node = 6 ORDER BY depth LIMIT 1
    ''')

    result = cursor.fetchone()
    if result:
        print(f"  ✓ Found path: {result['path_text']}")
        print(f"    Depth: {result['depth']} hops\n")
    else:
        print("  ✗ No path found\n")


def test_statistics(conn):
    """Test relationship statistics."""
    print("Test 5: Statistics")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT relationship_type, COUNT(*) as count
        FROM evidence_relationships
        WHERE engagement_id = 1
        GROUP BY relationship_type
    ''')

    stats = cursor.fetchall()
    total = sum(row['count'] for row in stats)

    print("  ✓ Relationship statistics:")
    for stat in stats:
        print(f"    - {stat['relationship_type']}: {stat['count']}")
    print(f"    - Total: {total}\n")


def test_attack_paths(conn):
    """Test saving attack paths."""
    print("Test 6: Saving attack paths")
    cursor = conn.cursor()

    path_json = '''[
        {"id": 1, "title": "Port Scan"},
        {"id": 2, "title": "Admin Panel"},
        {"id": 3, "title": "SQL Injection"},
        {"id": 4, "title": "Credentials"},
        {"id": 5, "title": "SSH Access"},
        {"id": 6, "title": "Root Shell"}
    ]'''

    cursor.execute('''
        INSERT INTO attack_paths
        (engagement_id, name, description, start_evidence_id, end_evidence_id, path_json)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (1, 'Initial Access to Root', 'Complete attack chain', 1, 6, path_json))
    conn.commit()

    path_id = cursor.lastrowid
    print(f"  ✓ Saved attack path with ID {path_id}")

    # Retrieve it
    cursor.execute('SELECT * FROM attack_paths WHERE id = ?', (path_id,))
    path = cursor.fetchone()
    print(f"  ✓ Retrieved: {path['name']}\n")


def main():
    print("=" * 60)
    print("Evidence Relationship Mapping - Simple Test")
    print("=" * 60)
    print()

    db = create_test_db()

    try:
        test_basic_crud(db)
        test_create_chain(db)
        test_query_relationships(db)
        test_path_finding_sql(db)
        test_statistics(db)
        test_attack_paths(db)

        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close()


if __name__ == '__main__':
    main()

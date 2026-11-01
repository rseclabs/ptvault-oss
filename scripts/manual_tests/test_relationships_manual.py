#!/usr/bin/env python3
"""
Manual test script for Evidence Relationship Mapping.

This script tests the relationship functionality without requiring pytest.
Run with: python3 test_relationships_manual.py
"""

import sqlite3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from models.dao.relationship_dao import RelationshipDAO, AttackPathDAO
# Import the migration module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "migration_013",
    os.path.join(os.path.dirname(__file__), "models/migrations/versions/013_evidence_relationships.py")
)
migration_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration_module)
upgrade = migration_module.upgrade


class MockG:
    """Mock Flask g object for testing."""
    def __init__(self, db, engagement_id=1, user_id=1):
        self.db = db
        self.active_engagement_id = engagement_id
        self.user_id = user_id


def create_test_db():
    """Create in-memory test database with sample data."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create required tables
    cursor.execute('''
        CREATE TABLE engagements (
            id INTEGER PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE evidence (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER,
            title TEXT,
            evidence_type TEXT,
            content TEXT,
            tags TEXT,
            host_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            email TEXT
        )
    ''')

    # Run relationship migration
    print("Running migration...")
    upgrade(conn)
    print("✓ Migration completed\n")

    # Insert test data
    cursor.execute("INSERT INTO engagements (id, name) VALUES (1, 'Test Engagement')")
    cursor.execute("INSERT INTO users (id, username, email) VALUES (1, 'testuser', 'test@example.com')")

    # Insert test evidence
    evidence_data = [
        (1, 1, 'Initial Port Scan', 'tool_output', 'Nmap scan found ports 22, 80, 443'),
        (2, 1, 'Found Admin Panel', 'note', 'Discovered /admin endpoint'),
        (3, 1, 'SQL Injection', 'screenshot', 'Found SQL injection in login form'),
        (4, 1, 'Database Credentials', 'command_output', 'Extracted admin:SecureP@ss123'),
        (5, 1, 'SSH Access', 'command_output', 'Successfully logged in via SSH'),
        (6, 1, 'Privilege Escalation', 'command_output', 'Used sudo vulnerability to get root'),
    ]

    cursor.executemany(
        'INSERT INTO evidence (id, engagement_id, title, evidence_type, content) VALUES (?, ?, ?, ?, ?)',
        evidence_data
    )

    conn.commit()
    return conn


def test_create_relationships(dao):
    """Test creating relationships."""
    print("Test 1: Creating relationships...")

    # Create attack chain
    rel1 = dao.create_relationship(1, 2, 'discovers', 'Port scan discovered admin panel')
    print(f"  ✓ Created relationship {rel1}: Port Scan -> Admin Panel")

    rel2 = dao.create_relationship(2, 3, 'leads_to', 'Admin panel led to SQL injection discovery')
    print(f"  ✓ Created relationship {rel2}: Admin Panel -> SQL Injection")

    rel3 = dao.create_relationship(3, 4, 'exploits', 'SQL injection exploited to extract credentials')
    print(f"  ✓ Created relationship {rel3}: SQL Injection -> Credentials")

    rel4 = dao.create_relationship(4, 5, 'uses', 'Used credentials for SSH access')
    print(f"  ✓ Created relationship {rel4}: Credentials -> SSH Access")

    rel5 = dao.create_relationship(5, 6, 'escalates', 'SSH access escalated to root')
    print(f"  ✓ Created relationship {rel5}: SSH Access -> Root Shell")

    print()
    return [rel1, rel2, rel3, rel4, rel5]


def test_get_relationships(dao):
    """Test getting relationships for evidence."""
    print("Test 2: Getting relationships for evidence...")

    # Get relationships for evidence #4 (Credentials)
    relationships = dao.get_relationships_for_evidence(4)

    print(f"  Evidence #4 has {len(relationships)} relationships:")
    for rel in relationships:
        direction = "→" if rel['source_evidence_id'] == 4 else "←"
        other_title = rel['target_title'] if rel['source_evidence_id'] == 4 else rel['source_title']
        print(f"    {direction} {rel['relationship_type']}: {other_title}")

    print()


def test_find_path(dao):
    """Test path finding."""
    print("Test 3: Finding attack path...")

    # Find path from initial scan (1) to root shell (6)
    path = dao.find_path(1, 6)

    if path:
        print(f"  ✓ Found path with {len(path)} steps:")
        for i, step in enumerate(path, 1):
            print(f"    {i}. {step['title']} ({step['evidence_type']})")
            if i < len(path):
                print(f"       └─ {step['edge_type']} →")
    else:
        print("  ✗ No path found")

    print()
    return path


def test_graph_data(dao):
    """Test getting graph data."""
    print("Test 4: Getting graph data...")

    graph = dao.get_graph_data()

    print(f"  ✓ Graph contains:")
    print(f"    - {len(graph['nodes'])} nodes (evidence items)")
    print(f"    - {len(graph['edges'])} edges (relationships)")

    print()


def test_statistics(dao):
    """Test relationship statistics."""
    print("Test 5: Getting statistics...")

    stats = dao.get_relationship_statistics()

    print("  ✓ Relationship statistics:")
    for rel_type, count in sorted(stats.items()):
        if rel_type != 'total':
            print(f"    - {rel_type}: {count}")
    print(f"    - Total: {stats['total']}")

    print()


def test_save_path(dao, path_data):
    """Test saving attack path."""
    print("Test 6: Saving attack path...")

    path_id = dao.save_path(
        name='Initial Access to Root',
        start_id=1,
        end_id=6,
        path_data=path_data,
        description='Complete attack chain from reconnaissance to privilege escalation'
    )

    print(f"  ✓ Saved attack path with ID {path_id}")

    # Retrieve it
    saved_path = dao.get_path(path_id)
    print(f"  ✓ Retrieved path: {saved_path['name']}")
    print(f"    - Steps: {len(saved_path['path_data'])}")

    print()


def test_delete_relationship(dao, rel_id):
    """Test deleting a relationship."""
    print("Test 7: Deleting a relationship...")

    deleted = dao.delete(rel_id)

    if deleted:
        print(f"  ✓ Deleted relationship {rel_id}")
    else:
        print(f"  ✗ Failed to delete relationship {rel_id}")

    print()


def main():
    """Run all tests."""
    print("=" * 60)
    print("Evidence Relationship Mapping - Manual Test Suite")
    print("=" * 60)
    print()

    # Create test database
    db = create_test_db()

    # Mock Flask g
    mock_g = MockG(db, engagement_id=1, user_id=1)

    # Monkey-patch Flask g
    import flask
    flask.g = mock_g

    # Create DAO instances
    rel_dao = RelationshipDAO()
    path_dao = AttackPathDAO()

    try:
        # Run tests
        rel_ids = test_create_relationships(rel_dao)
        test_get_relationships(rel_dao)
        path = test_find_path(rel_dao)
        test_graph_data(rel_dao)
        test_statistics(rel_dao)

        if path:
            test_save_path(path_dao, path)

        if rel_ids:
            test_delete_relationship(rel_dao, rel_ids[0])

        print("=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close()


if __name__ == '__main__':
    main()

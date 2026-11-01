#!/usr/bin/env python3
"""
Test script to demonstrate composite index performance improvements.
Shows EXPLAIN QUERY PLAN output for common queries before and after index creation.
"""

import os
import sys
from models.database import get_db_connection, init_db, run_migrations


def analyze_query_plan(cursor, query, params=None, description=""):
    """Execute EXPLAIN QUERY PLAN and display results."""
    print(f"\n{'='*80}")
    print(f"Query: {description}")
    print(f"{'='*80}")
    print(f"SQL: {query}")
    if params:
        print(f"Params: {params}")

    try:
        if params:
            cursor.execute(f"EXPLAIN QUERY PLAN {query}", params)
        else:
            cursor.execute(f"EXPLAIN QUERY PLAN {query}")

        print("\nExecution Plan:")
        for row in cursor.fetchall():
            # Format: (id, parent, notused, detail)
            indent = "  " * (row[0] if row[0] else 0)
            print(f"{indent}{row[3]}")
    except Exception as e:
        print(f"Error analyzing query: {e}")


def test_query_performance():
    """Test and display query plans for optimized queries."""

    print("\n" + "="*80)
    print("PTVault Composite Index Performance Analysis")
    print("="*80)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create sample data
    print("\nSetting up test data...")
    cursor.execute("INSERT INTO engagements (id, name, client_name) VALUES (1, 'Test Engagement', 'Test Client')")
    cursor.execute("INSERT INTO evidence (engagement_id, evidence_type, title, content) VALUES (1, 'note', 'Test Note', 'Test content')")
    cursor.execute("INSERT INTO evidence (engagement_id, evidence_type, title, content) VALUES (1, 'screenshot', 'Test Screenshot', 'Test content')")
    cursor.execute("INSERT INTO hosts (id, engagement_id, ip) VALUES (1, 1, '192.168.1.1')")
    cursor.execute("INSERT INTO host_ports (host_id, port, protocol) VALUES (1, 80, 'tcp')")
    cursor.execute("INSERT INTO host_ports (host_id, port, protocol) VALUES (1, 443, 'tcp')")
    cursor.execute("INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, status) VALUES (1, 1, 1, 'completed')")
    conn.commit()

    print("Test data created.\n")

    # Query 1: Evidence filtering by engagement and type
    analyze_query_plan(
        cursor,
        "SELECT * FROM evidence WHERE engagement_id = ? AND evidence_type = ?",
        (1, 'note'),
        "Evidence filtered by engagement and type (idx_evidence_engagement_type)"
    )

    # Query 2: Evidence with sorting by date
    analyze_query_plan(
        cursor,
        "SELECT * FROM evidence WHERE engagement_id = ? ORDER BY created_at DESC",
        (1,),
        "Evidence sorted by date (idx_evidence_engagement_created)"
    )

    # Query 3: Host lookup by engagement and IP
    analyze_query_plan(
        cursor,
        "SELECT * FROM hosts WHERE engagement_id = ? AND ip = ?",
        (1, '192.168.1.1'),
        "Host lookup by engagement and IP (idx_hosts_engagement_ip)"
    )

    # Query 4: Evidence-host junction lookup
    analyze_query_plan(
        cursor,
        """SELECT e.* FROM evidence e
           JOIN evidence_hosts eh ON e.id = eh.evidence_id
           WHERE eh.host_id = ?""",
        (1,),
        "Evidence joined with hosts (idx_evidence_hosts_host_evidence)"
    )

    # Query 5: Host ports with sorting
    analyze_query_plan(
        cursor,
        "SELECT * FROM host_ports WHERE host_id = ? ORDER BY port ASC",
        (1,),
        "Host ports sorted by port number (idx_host_ports_host_port)"
    )

    # Query 6: Test executions by engagement and status
    analyze_query_plan(
        cursor,
        "SELECT * FROM test_executions WHERE engagement_id = ? AND status = ?",
        (1, 'completed'),
        "Test executions filtered by status (idx_test_executions_engagement_status)"
    )

    # Show index information
    print("\n" + "="*80)
    print("Index Statistics")
    print("="*80)

    cursor.execute("""
        SELECT
            name,
            tbl_name,
            sql
        FROM sqlite_master
        WHERE type='index'
        AND name LIKE 'idx_%'
        AND name IN (
            'idx_evidence_engagement_type',
            'idx_evidence_engagement_created',
            'idx_hosts_engagement_ip',
            'idx_evidence_hosts_host_evidence',
            'idx_host_ports_host_port',
            'idx_test_executions_engagement_status'
        )
        ORDER BY name
    """)

    print("\nComposite indexes created:")
    for row in cursor.fetchall():
        index_name = row[0]
        table_name = row[1]
        index_sql = row[2]
        print(f"\n  {index_name} (on {table_name})")
        print(f"    {index_sql}")

    print("\n" + "="*80)
    print("Performance Expectations")
    print("="*80)
    print("""
Composite indexes provide the following benefits:

1. idx_evidence_engagement_type
   - Optimizes filtering evidence by engagement AND type
   - Expected improvement: 2-3x faster
   - Use case: Filtering screenshots, notes, etc. per engagement

2. idx_evidence_engagement_created
   - Eliminates sort operation when ordering by date
   - Expected improvement: 2-5x faster for large datasets
   - Use case: Evidence timeline view

3. idx_hosts_engagement_ip
   - Speeds up host lookup during tool import
   - Expected improvement: 2-3x faster
   - Use case: Nmap/Nessus import processing

4. idx_evidence_hosts_host_evidence
   - Optimizes evidence retrieval for a specific host
   - Expected improvement: 2-3x faster
   - Use case: Loading host detail page

5. idx_host_ports_host_port
   - Eliminates sort operation for port listings
   - Expected improvement: Instant sort for port grids
   - Use case: Port grid view

6. idx_test_executions_engagement_status
   - Speeds up filtering test executions by status
   - Expected improvement: 2-3x faster
   - Use case: Viewing pending/completed tests

Note: Actual performance gains depend on data volume.
Improvements are most noticeable with 1000+ records per table.
""")

    # Clean up
    conn.close()
    print("\nAnalysis complete!")


if __name__ == '__main__':
    # Use a test database
    test_db = './data/test_performance.db'

    # Remove if exists
    if os.path.exists(test_db):
        os.remove(test_db)

    # Temporarily override the config
    import config
    original_db = config.Config.DATABASE_PATH
    config.Config.DATABASE_PATH = test_db

    try:
        # Initialize and run migrations
        print("Initializing database with composite indexes...")
        init_db()
        run_migrations()

        # Run performance tests
        test_query_performance()

    finally:
        # Restore original config
        config.Config.DATABASE_PATH = original_db

        # Clean up test database
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"\nTest database cleaned up: {test_db}")

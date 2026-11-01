"""
Migration 009: Add Composite Indexes

Adds composite indexes for query performance optimization.

Indexes added:
- idx_evidence_engagement_type: Evidence filtering by engagement and type
- idx_evidence_engagement_created: Evidence sorting by engagement and date
- idx_hosts_engagement_ip: Host lookup by engagement and IP
- idx_evidence_hosts_host_evidence: Evidence-host junction queries
- idx_host_ports_host_port: Port listings with ordering
- idx_test_executions_engagement_status: Test execution status filtering

Created: 2026-02-09
"""


def upgrade(db):
    """Apply the migration."""
    cursor = db.cursor()

    # Check if indexes already exist before creating
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    existing_indexes = {row[0] for row in cursor.fetchall()}

    indexes_created = 0

    # Composite index for evidence filtering by engagement and type
    # Optimizes: WHERE engagement_id = ? AND evidence_type = ?
    # Query pattern: routes/evidence.py:360-374 (list_evidence)
    # Expected improvement: 2-3x faster filtering by type within an engagement
    if 'idx_evidence_engagement_type' not in existing_indexes:
        cursor.execute('CREATE INDEX idx_evidence_engagement_type ON evidence(engagement_id, evidence_type)')
        indexes_created += 1
        print("  - Created idx_evidence_engagement_type")

    # Composite index for evidence sorting by engagement and creation date
    # Optimizes: WHERE engagement_id = ? ORDER BY created_at DESC
    # Query pattern: routes/evidence.py:374 (list_evidence with ORDER BY)
    # Expected improvement: Eliminates sort operation, 2-5x faster for large datasets
    if 'idx_evidence_engagement_created' not in existing_indexes:
        cursor.execute('CREATE INDEX idx_evidence_engagement_created ON evidence(engagement_id, created_at DESC)')
        indexes_created += 1
        print("  - Created idx_evidence_engagement_created")

    # Composite index for hosts lookup by engagement and IP
    # Optimizes: WHERE engagement_id = ? AND ip = ?
    # Query pattern: routes/hosts.py:185-192, utils/host_extractor.py (get_or_create_host)
    # Expected improvement: 2-3x faster host lookup during tool import
    if 'idx_hosts_engagement_ip' not in existing_indexes:
        cursor.execute('CREATE INDEX idx_hosts_engagement_ip ON hosts(engagement_id, ip)')
        indexes_created += 1
        print("  - Created idx_hosts_engagement_ip")

    # Composite index for evidence-host junction table lookups
    # Optimizes: JOIN evidence_hosts ON e.id = eh.evidence_id WHERE eh.host_id = ?
    # Query pattern: routes/hosts.py:123-132 (get_host with evidence)
    # Expected improvement: 2-3x faster when loading host evidence
    if 'idx_evidence_hosts_host_evidence' not in existing_indexes:
        cursor.execute('CREATE INDEX idx_evidence_hosts_host_evidence ON evidence_hosts(host_id, evidence_id)')
        indexes_created += 1
        print("  - Created idx_evidence_hosts_host_evidence")

    # Composite index for host_ports lookup by host
    # Optimizes: WHERE host_id = ? ORDER BY port ASC
    # Query pattern: routes/hosts.py:609-614 (list_ports)
    # Expected improvement: Eliminates sort operation for port listings
    if 'idx_host_ports_host_port' not in existing_indexes:
        cursor.execute('CREATE INDEX idx_host_ports_host_port ON host_ports(host_id, port ASC)')
        indexes_created += 1
        print("  - Created idx_host_ports_host_port")

    # Composite index for test_executions by engagement and status
    # Optimizes: WHERE engagement_id = ? AND status = ?
    # Query pattern: Common for filtering executions by status in test plans
    # Expected improvement: 2-3x faster execution status filtering
    if 'idx_test_executions_engagement_status' not in existing_indexes:
        cursor.execute('CREATE INDEX idx_test_executions_engagement_status ON test_executions(engagement_id, status)')
        indexes_created += 1
        print("  - Created idx_test_executions_engagement_status")

    db.commit()

    if indexes_created > 0:
        print(f"  ✓ Created {indexes_created} composite index(es)")
    else:
        print("  ✓ All composite indexes already exist")


def downgrade(db):
    """Rollback the migration."""
    cursor = db.cursor()

    # Drop composite indexes
    cursor.execute('DROP INDEX IF EXISTS idx_test_executions_engagement_status')
    cursor.execute('DROP INDEX IF EXISTS idx_host_ports_host_port')
    cursor.execute('DROP INDEX IF EXISTS idx_evidence_hosts_host_evidence')
    cursor.execute('DROP INDEX IF EXISTS idx_hosts_engagement_ip')
    cursor.execute('DROP INDEX IF EXISTS idx_evidence_engagement_created')
    cursor.execute('DROP INDEX IF EXISTS idx_evidence_engagement_type')

    db.commit()
    print("  ✓ Composite indexes removed")

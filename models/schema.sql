-- Users table (multi-user with RBAC)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'tester',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Engagement members (team assignments with RBAC)
CREATE TABLE IF NOT EXISTS engagement_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'tester',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by INTEGER,
    UNIQUE(engagement_id, user_id),
    FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_engagement_members_engagement ON engagement_members(engagement_id);
CREATE INDEX IF NOT EXISTS idx_engagement_members_user ON engagement_members(user_id);

-- Audit log for security and compliance
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    engagement_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id INTEGER,
    details TEXT,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_engagement ON audit_log(engagement_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, timestamp DESC);

-- User sessions (track active sessions)
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

-- Teams table
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Team members
CREATE TABLE IF NOT EXISTS team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('lead', 'member')),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by INTEGER,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by) REFERENCES users(id),
    UNIQUE(team_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id);

-- Engagements table
CREATE TABLE IF NOT EXISTS engagements (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    client_name TEXT,
    short_name TEXT,
    description TEXT,
    tags TEXT,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'active',
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    team_id INTEGER REFERENCES teams(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for efficient status filtering
CREATE INDEX IF NOT EXISTS idx_engagements_status ON engagements(status);
CREATE INDEX IF NOT EXISTS idx_engagements_team ON engagements(team_id);

-- Evidence table
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL,
    evidence_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    tags TEXT,
    file_path TEXT,
    file_name TEXT,
    file_size INTEGER,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(engagement_id) REFERENCES engagements(id)
);

-- Index for efficient engagement filtering
CREATE INDEX IF NOT EXISTS idx_evidence_engagement ON evidence(engagement_id);

-- Index for efficient evidence type filtering
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence(evidence_type);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Junction table for evidence-tags relationship
CREATE TABLE IF NOT EXISTS evidence_tags (
    evidence_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (evidence_id, tag_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Indexes for efficient tag queries
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_evidence_tags_evidence ON evidence_tags(evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_tags_tag ON evidence_tags(tag_id);

-- Hosts table (unique per engagement by IP)
CREATE TABLE IF NOT EXISTS hosts (
    id INTEGER PRIMARY KEY,
    engagement_id INTEGER NOT NULL,
    ip TEXT NOT NULL,
    hostname TEXT,
    os TEXT,
    notes TEXT,
    rooted INTEGER DEFAULT 0,
    shell INTEGER DEFAULT 0,
    interested INTEGER DEFAULT 0,
    not_interested INTEGER DEFAULT 0,
    out_of_scope INTEGER DEFAULT 0,
    flagged INTEGER DEFAULT 0,
    reviewed INTEGER DEFAULT 0,
    color_category TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
    UNIQUE(engagement_id, ip)
);

-- Junction table for evidence-host relationship
CREATE TABLE IF NOT EXISTS evidence_hosts (
    evidence_id INTEGER NOT NULL,
    host_id INTEGER NOT NULL,
    source TEXT DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (evidence_id, host_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE CASCADE
);

-- Indexes for efficient host queries
CREATE INDEX IF NOT EXISTS idx_hosts_engagement ON hosts(engagement_id);
CREATE INDEX IF NOT EXISTS idx_hosts_ip ON hosts(ip);
CREATE INDEX IF NOT EXISTS idx_evidence_hosts_evidence ON evidence_hosts(evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_hosts_host ON evidence_hosts(host_id);

-- Host notes with markdown support
CREATE TABLE IF NOT EXISTS host_notes (
    id INTEGER PRIMARY KEY,
    host_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(host_id) REFERENCES hosts(id) ON DELETE CASCADE
);

-- Host ports (from tool parsing + manual entry)
CREATE TABLE IF NOT EXISTS host_ports (
    id INTEGER PRIMARY KEY,
    host_id INTEGER NOT NULL,
    port INTEGER NOT NULL,
    protocol TEXT DEFAULT 'tcp',
    state TEXT DEFAULT 'open',
    service TEXT,
    version TEXT,
    source TEXT DEFAULT 'manual',
    evidence_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(host_id) REFERENCES hosts(id) ON DELETE CASCADE,
    FOREIGN KEY(evidence_id) REFERENCES evidence(id) ON DELETE SET NULL,
    UNIQUE(host_id, port, protocol)
);

-- Host credentials
CREATE TABLE IF NOT EXISTS host_credentials (
    id INTEGER PRIMARY KEY,
    host_id INTEGER NOT NULL,
    username TEXT,
    password TEXT,
    password_type TEXT DEFAULT 'cleartext',
    hash_type TEXT,
    service TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(host_id) REFERENCES hosts(id) ON DELETE CASCADE
);

-- Indexes for host detail tables
CREATE INDEX IF NOT EXISTS idx_host_notes_host ON host_notes(host_id);
CREATE INDEX IF NOT EXISTS idx_host_ports_host ON host_ports(host_id);
CREATE INDEX IF NOT EXISTS idx_host_credentials_host ON host_credentials(host_id);

-- FTS virtual table for full-text search
-- NOTE: Using FTS4 (not FTS5) due to pysqlcipher3 limitation
-- FTS5 is not compiled in pysqlcipher3. FTS4 provides similar functionality
-- with slightly lower performance (~30% slower) but same features needed.
CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts4(
    title,
    content,
    metadata,
    tokenize=unicode61
);

-- Sync trigger: INSERT - Keep FTS index synchronized
CREATE TRIGGER IF NOT EXISTS evidence_fts_insert
AFTER INSERT ON evidence
BEGIN
    INSERT INTO evidence_fts(docid, title, content, metadata)
    VALUES (new.id, new.title, new.content, new.metadata);
END;

-- Sync trigger: UPDATE - Keep FTS index synchronized
CREATE TRIGGER IF NOT EXISTS evidence_fts_update
AFTER UPDATE ON evidence
BEGIN
    UPDATE evidence_fts
    SET title = new.title,
        content = new.content,
        metadata = new.metadata
    WHERE docid = old.id;
END;

-- Sync trigger: DELETE - Keep FTS index synchronized
CREATE TRIGGER IF NOT EXISTS evidence_fts_delete
AFTER DELETE ON evidence
BEGIN
    DELETE FROM evidence_fts WHERE docid = old.id;
END;

-- Generated columns for JSON metadata optimization
-- These columns extract frequently-queried JSON fields for efficient filtering
-- NOTE: Generated columns require SQLite 3.31+
-- Check if columns already exist before adding (for migration safety)

-- Add tool_name generated column
-- This column is only added if it doesn't exist
-- It extracts the 'tool' field from the metadata JSON

-- Add severity_level generated column
-- This column is only added if it doesn't exist
-- It extracts the highest severity level from metadata.summary.by_severity

-- ============================================
-- TEST PLANS FEATURE TABLES
-- ============================================

-- Atomics library (global, not engagement-specific)
-- Stores parsed Atomic Red Team test data
CREATE TABLE IF NOT EXISTS atomics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    technique_id TEXT NOT NULL,
    technique_name TEXT NOT NULL,
    tactic TEXT,
    atomic_test_index INTEGER NOT NULL,
    atomic_test_name TEXT NOT NULL,
    description TEXT,
    supported_platforms TEXT,
    executor_name TEXT,
    executor_command TEXT,
    executor_cleanup TEXT,
    input_arguments TEXT,
    dependencies TEXT,
    elevation_required INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(technique_id, atomic_test_index)
);

CREATE INDEX IF NOT EXISTS idx_atomics_technique ON atomics(technique_id);
CREATE INDEX IF NOT EXISTS idx_atomics_tactic ON atomics(tactic);
CREATE INDEX IF NOT EXISTS idx_atomics_executor ON atomics(executor_name);

-- Atomics metadata (singleton row)
CREATE TABLE IF NOT EXISTS atomics_metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version TEXT,
    last_updated TIMESTAMP,
    total_techniques INTEGER DEFAULT 0,
    total_tests INTEGER DEFAULT 0,
    download_path TEXT
);

-- Test plans (independent of engagements - reusable templates)
CREATE TABLE IF NOT EXISTS test_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    target_platform TEXT DEFAULT 'all',
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_test_plans_platform ON test_plans(target_platform);

-- Test plan items
CREATE TABLE IF NOT EXISTS test_plan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_plan_id INTEGER NOT NULL,
    atomic_id INTEGER,
    custom_name TEXT,
    custom_command TEXT,
    custom_platform TEXT,
    sort_order INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    input_overrides TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_plan_id) REFERENCES test_plans(id) ON DELETE CASCADE,
    FOREIGN KEY (atomic_id) REFERENCES atomics(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_test_plan_items_plan ON test_plan_items(test_plan_id);
CREATE INDEX IF NOT EXISTS idx_test_plan_items_atomic ON test_plan_items(atomic_id);

-- Navigator layers (stored imported MITRE ATT&CK Navigator layers)
CREATE TABLE IF NOT EXISTS navigator_layers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    domain TEXT DEFAULT 'enterprise-attack',
    layer_json TEXT NOT NULL,
    technique_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_navigator_layers_domain ON navigator_layers(domain);

-- Test executions (engagement-specific tracking)
CREATE TABLE IF NOT EXISTS test_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL,
    test_plan_id INTEGER NOT NULL,
    test_plan_item_id INTEGER NOT NULL,
    host_id INTEGER,
    status TEXT DEFAULT 'pending',
    execution_started_at TIMESTAMP,
    execution_completed_at TIMESTAMP,
    execution_output TEXT,
    execution_notes TEXT,
    evidence_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE CASCADE,
    FOREIGN KEY (test_plan_id) REFERENCES test_plans(id) ON DELETE CASCADE,
    FOREIGN KEY (test_plan_item_id) REFERENCES test_plan_items(id) ON DELETE CASCADE,
    FOREIGN KEY (host_id) REFERENCES hosts(id) ON DELETE SET NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_test_executions_engagement ON test_executions(engagement_id);
CREATE INDEX IF NOT EXISTS idx_test_executions_plan ON test_executions(test_plan_id);
CREATE INDEX IF NOT EXISTS idx_test_executions_status ON test_executions(status)

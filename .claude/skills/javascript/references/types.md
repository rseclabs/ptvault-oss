# JavaScript Types Reference

## Contents
- Data Structures
- API Response Shapes
- State Object Shapes
- Type Coercion Gotchas
- JSDoc Conventions

---

## Data Structures

### Engagement Object

```javascript
const engagement = {
    id: 1,
    name: 'ACME Corp Pentest',
    client_name: 'ACME Corporation',
    short_name: 'ACME-EXT',
    status: 'active',           // 'active' | 'completed' | 'archived'
    start_date: '2025-12-01',
    end_date: '2025-12-15',
    contact_name: 'John Smith',
    contact_email: 'john@acme.com',
    description: 'External network assessment',
    tags: 'external,network',   // Comma-separated string, NOT array
    created_at: '2025-12-01T10:00:00Z',
    updated_at: '2025-12-01T10:00:00Z'
};
```

### Host Object

```javascript
const host = {
    id: 42,
    engagement_id: 1,
    ip: '192.168.1.100',
    hostname: 'webserver01',    // Can be null
    os: 'Linux',                // Can be null
    evidence_count: 5,
    // Indicators — SQLite returns 0/1 integers, NOT booleans
    rooted: 0,
    shell: 1,
    interested: 1,
    not_interested: 0,
    out_of_scope: 0,
    flagged: 0,
    reviewed: 0,
    color_category: 'red'      // null | 'red' | 'yellow' | 'green' | 'blue' | ...
};
```

### Evidence Object

```javascript
const evidence = {
    id: 100,
    engagement_id: 1,
    host_id: 42,               // null for "General" section evidence
    evidence_type: 'note',     // 'note' | 'screenshot' | 'command_output' | 'tool_output'
    title: 'SQL Injection Found',
    content: 'Markdown content...',
    tags: 'critical,sqli,web', // Comma-separated string
    file_path: null,           // Populated for file-based evidence
    file_name: null,           // Original filename
    metadata: '{}',            // JSON string — must JSON.parse() before use
    severity_level: 'critical',// null | 'critical' | 'high' | 'medium' | 'low' | 'info'
    tool_name: 'nmap',         // null | tool identifier
    created_at: '2025-12-01T10:00:00Z'
};
```

### Writeup Object

```javascript
const writeup = {
    id: 10,
    name: 'SQL Injection',
    writeup_type: 'finding',   // 'finding' | 'narrative'
    category: 'Injection',
    criticality: 'critical',   // Only for findings
    cvss_score: 9.8,           // Only for findings, 0.0-10.0
    description: 'Markdown...',
    remediation: 'Markdown...', // Only for findings
    tags: 'owasp,injection'
};
```

---

## API Response Shapes

### List Endpoints — Inconsistent Wrapping

Some endpoints return bare arrays, others return wrapped objects:

```javascript
// GET /api/engagements → bare array
const engagements = await API.engagements.getAll();
// engagements = [{id: 1, ...}, {id: 2, ...}]

// GET /api/hosts → wrapped object
const data = await API.hosts.getAll();
// data = { hosts: [...], general_count: 5 }

// GET /api/evidence → bare array
const evidence = await API.evidence.getAll();
// evidence = [{id: 100, ...}]
```

Always check the actual API module to verify the response shape.

### Error Response — Consistent

```javascript
// All errors from Flask:
{ "error": "Human-readable error message" }

// apiRequest throws Error with this message, so catch blocks get:
// error.message === "Human-readable error message"
```

### Create/Update Response — Returns Full Object

```javascript
const newHost = await API.hosts.create({ ip: '10.0.0.1' });
// newHost = { id: 43, ip: '10.0.0.1', engagement_id: 1, ... }
```

---

## State Object Shapes

### AppState (app.js)

```javascript
const AppState = {
    activeEngagement: null,          // Engagement object or null
    engagements: [],                 // Array of engagement objects
    searchQuery: '',
    filters: {
        severity: [],                // ['critical', 'high']
        type: []                     // ['note', 'screenshot']
    },
    pendingSwitchEngagementId: null  // Used for switch confirmation modal
};
```

### HostManager (hosts.js)

```javascript
const HostManager = {
    selectedHostId: null,            // null | 'general' | number
    hosts: [],
    generalCount: 0,
    currentEvidence: [],
    currentNotes: [],
    currentPorts: [],
    currentCredentials: [],
    currentVulnerabilities: [],
    currentHostTab: 'indicators',    // Sub-tab within host detail
    currentGeneralTab: 'notes',      // Sub-tab within General section
    hostSeverityMap: {},             // { hostId: { critical: 0, high: 1, ... } }
    severityFilter: null,            // null | 'critical' | 'high' | ...
    selectedEvidenceIds: new Set(),  // Bulk selection
    bulkOperationInProgress: false
};
```

### ReportingManager (reporting.js)

```javascript
const ReportingManager = {
    initialized: false,
    activeTab: 'writeups',           // 'writeups' | 'reports' | 'templates'
    writeups: [],
    currentReport: null,             // { id, name, structure }
    workspaceItems: [],              // Ordered items in report workspace
    dragState: {
        draggedItem: null,
        draggedFrom: null,           // 'source' | 'workspace'
        draggedIndex: null
    }
};
```

### Filter Object Convention

Used across multiple managers — `'all'` means no filter:

```javascript
const filters = {
    category: 'all',
    criticality: 'all',
    search: '',
    platform: 'all',
    tactic: 'all'
};
```

---

## Type Coercion Gotchas

### SQLite Booleans Are 0/1 Integers

See the **sqlite** skill for details. SQLite has no boolean type.

```javascript
// BAD - Works by coincidence (truthy), but unclear intent
if (host.rooted) { ... }

// GOOD - Explicit comparison
if (host.rooted === 1) { ... }

// GOOD - Convert to boolean
const isRooted = !!host.rooted;
```

### Tags Are Comma-Separated Strings

```javascript
// Parse tags for rendering
function parseTags(tagString) {
    if (!tagString) return [];
    return tagString.split(',').map(t => t.trim()).filter(Boolean);
}

// Join tags for API submission
const tags = ['critical', 'sqli'].join(',');
```

### Metadata Is a JSON String

```javascript
// Parse metadata for display
const meta = evidence.metadata ? JSON.parse(evidence.metadata) : {};

// Serialize metadata for submission
const metadata = JSON.stringify({ severity_level: 'critical', cvss: 9.8 });
```

### Null vs Empty String

API returns `null` for unset optional fields. Use fallback:

```javascript
const hostname = host.hostname || '';
const tags = evidence.tags || '';
const description = writeup.description || '';
```

---

## JSDoc Conventions

Use JSDoc for function documentation — provides IDE autocomplete:

```javascript
/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {'success'|'error'|'warning'|'info'} type - Toast type
 * @param {number} [duration=3000] - Duration in ms
 */
function showToast(message, type = 'info', duration = 3000) { ... }
```

```javascript
/**
 * @param {Object} evidenceData
 * @param {string} evidenceData.title - Evidence title
 * @param {string} evidenceData.evidence_type - Type identifier
 * @param {string} [evidenceData.tags] - Comma-separated tags
 * @param {File} [file] - Optional file attachment
 * @returns {Promise<Object>} Created evidence object
 */
async create(evidenceData, file = null) { ... }
```

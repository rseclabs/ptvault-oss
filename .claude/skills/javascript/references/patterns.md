# JavaScript Patterns Reference

## Contents
- Async/Await Patterns
- Rendering and DOM Manipulation
- Event Handling
- State Management
- API Integration
- Anti-Patterns

---

## Async/Await Patterns

### Sequential Initialization

The app boots in strict order — engagement context must exist before loading hosts:

```javascript
document.addEventListener('DOMContentLoaded', async () => {
    ThemeManager.init();
    initKeyboardShortcuts();
    setupEventListeners();
    await loadEngagements();
    await loadActiveEngagement();

    if (AppState.activeEngagement) {
        await HostManager.init();
        await refreshEvidenceStats();
    }
});
```

### Parallel Loading When Independent

```javascript
// GOOD - Load independent data in parallel
async selectHost(hostId) {
    this.selectedHostId = hostId;
    this.renderHostList();

    if (hostId !== 'general') {
        await Promise.all([
            this.loadNotes(hostId),
            this.loadPorts(hostId),
            this.loadCredentials(hostId),
            this.loadVulnerabilities(hostId)
        ]);
    }
}
```

### WARNING: Fire-and-Forget Async Calls

**The Problem:**

```javascript
// BAD - Missing await, errors vanish silently
document.addEventListener('DOMContentLoaded', async () => {
    loadEngagements();  // No await — race condition with loadActive
    loadActiveEngagement();
});
```

**Why This Breaks:**
1. Errors are swallowed — users see broken UI with zero feedback
2. `loadActiveEngagement` may run before engagements finish loading
3. Impossible to debug without console open

**The Fix:**

```javascript
// GOOD - Explicit ordering with await
await loadEngagements();
await loadActiveEngagement();
```

---

## Rendering and DOM Manipulation

### Template Literal List Rendering

The primary pattern: `.map().join('')` with full innerHTML replacement.

```javascript
renderHostList() {
    const container = document.getElementById('hostsList');
    if (!container) return;

    if (this.hosts.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No hosts yet</p></div>';
        return;
    }

    container.innerHTML = this.hosts.map(host => `
        <div class="host-item ${this.selectedHostId === host.id ? 'active' : ''}"
             data-host-id="${host.id}"
             onclick="HostManager.selectHost(${host.id})">
            ${host.color_category ? `<div class="host-color-badge" data-color="${host.color_category}"></div>` : ''}
            <span class="host-name">${escapeHtml(host.ip)}</span>
            <span class="host-meta">${escapeHtml(host.hostname || '')}</span>
            ${this.renderIndicatorBadges(host)}
        </div>
    `).join('');

    // REQUIRED: Re-init Lucide icons after innerHTML replacement
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}
```

### WARNING: innerHTML Without escapeHtml

**The Problem:**

```javascript
// BAD - XSS vulnerability: user-controlled content rendered raw
container.innerHTML = `<div>${host.hostname}</div>`;
```

**Why This Breaks:**
A hostname like `<img src=x onerror=alert(1)>` executes JavaScript. In a pentest tool handling adversary-controlled data (Nmap hostnames, Nessus output), this is especially dangerous.

**The Fix:**

```javascript
// GOOD - Always escape user content
container.innerHTML = `<div>${escapeHtml(host.hostname)}</div>`;
```

**When You Might Be Tempted:**
When rendering data you "know" is safe (like IPs). Don't — tool parsers can produce unexpected strings.

### Guard Clause for Missing Elements

ALWAYS check element existence before manipulation:

```javascript
// GOOD
function updateHeader(title) {
    const el = document.getElementById('pageHeader');
    if (!el) return;
    el.textContent = title;
}
```

### Tab Switching with classList

```javascript
switchHostTab(tabName) {
    this.currentHostTab = tabName;

    document.querySelectorAll('.host-sub-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.subtab === tabName);
    });

    const tabMap = {
        'indicators': 'indicatorsSection',
        'notes': 'notesSection',
        'ports': 'portsSection',
        'findings': 'vulnerabilitiesSection',
        'credentials': 'credentialsSection'
    };

    Object.values(tabMap).forEach(id => {
        const section = document.getElementById(id);
        if (section) section.classList.remove('active');
    });

    const activeSection = document.getElementById(tabMap[tabName]);
    if (activeSection) activeSection.classList.add('active');
}
```

---

## Event Handling

### Inline Handlers for Dynamic Content

Dynamic HTML uses inline `onclick` referencing global Manager objects:

```javascript
// Rendered in template literal
onclick="HostManager.selectHost(${host.id})"
onclick="event.stopPropagation(); handleEditEngagement(${eng.id})"
```

Functions must be globally accessible:

```javascript
window.handleEditEngagement = handleEditEngagement;
window.confirmEngagementSwitch = confirmEngagementSwitch;
```

### WARNING: Inline `this` Context

**The Problem:**

```javascript
// BAD - 'this' in inline handler refers to the DOM element, not your object
container.innerHTML = `<button onclick="this.handleClick()">Click</button>`;
```

**The Fix:**

```javascript
// GOOD - Reference the Manager object by name
container.innerHTML = `<button onclick="HostManager.handleClick(${id})">Click</button>`;
```

### Programmatic Listeners for Static Elements

```javascript
function setupEventListeners() {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            try {
                await API.auth.logout();
                window.location.href = '/';
            } catch (error) {
                showToast('Logout failed: ' + error.message, 'error');
            }
        });
    }
}
```

### Debounced Search

```javascript
const searchInput = document.getElementById('searchInput');
if (searchInput) {
    searchInput.addEventListener('input', debounce(handleSearch, 300));
}
```

---

## State Management

### AppState for Cross-Module Context

```javascript
const AppState = {
    activeEngagement: null,
    engagements: [],
    searchQuery: '',
    filters: { severity: [], type: [] },
    pendingSwitchEngagementId: null
};
```

Mutated directly — no proxies or observables. After mutation, you MUST re-render manually.

### Manager Objects Own Their Domain State

```javascript
const HostManager = {
    selectedHostId: null,     // null | 'general' | number
    hosts: [],
    currentPorts: [],
    selectedEvidenceIds: new Set(),

    async loadHosts() {
        try {
            const data = await API.hosts.getAll();
            this.hosts = data.hosts || [];
            this.renderHostList();
        } catch (error) {
            this.hosts = [];
            this.renderHostList();
        }
    }
};
```

### WARNING: Updating State Without Re-Rendering

**The Problem:**

```javascript
// BAD - Data updated, UI shows stale state
async function updateHost(id, data) {
    await API.hosts.update(id, data);
    // Forgot to re-render
}
```

**The Fix:**

```javascript
// GOOD - Always re-fetch and re-render after mutation
async function updateHost(id, data) {
    await API.hosts.update(id, data);
    await HostManager.loadHosts();  // Re-fetches and calls renderHostList()
}
```

---

## API Integration

### Using the apiRequest Singleton

All API modules import from `static/js/lib/request.js`:

```javascript
import { apiRequest } from '../lib/request.js';

export const HostsAPI = {
    async getAll() {
        return apiRequest.get('/hosts');
    },
    async create(hostData) {
        return apiRequest.post('/hosts', hostData);
    },
    async update(id, updates) {
        return apiRequest.put(`/hosts/${id}`, updates);
    },
    async delete(id) {
        return apiRequest.delete(`/hosts/${id}`);
    }
};
```

`apiRequest` handles JSON serialization, content-type detection, error throwing, and credentials. See the **flask** skill for corresponding backend routes.

### Query Parameters

```javascript
async search(params) {
    return apiRequest.get('/evidence/search', { params });
}
// Produces: GET /api/evidence/search?q=sqli&tags=critical
```

### Blob Downloads

```javascript
async exportPdf(reportId) {
    const blob = await apiRequest.get(`/reporting/reports/${reportId}/export/pdf`);
    downloadBlob(blob, 'report.pdf');
}
```

`apiRequest.handleResponse()` auto-detects blob content types and returns a Blob object.

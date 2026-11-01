# JavaScript Modules Reference

## Contents
- File Organization
- API Layer Architecture
- Manager Module Pattern
- Inter-Module Communication
- Module Loading Order
- Adding a New Feature

---

## File Organization

```
static/js/
├── lib/
│   └── request.js          # APIRequest class — base fetch wrapper
├── api/                    # Modular API layer (15 modules)
│   ├── auth.js             # AuthAPI
│   ├── engagements.js      # EngagementsAPI
│   ├── evidence.js         # EvidenceAPI
│   ├── hosts.js            # HostsAPI
│   ├── reporting.js        # ReportingAPI
│   ├── testplans.js        # TestPlansAPI
│   ├── commands.js         # CommandsAPI
│   ├── admin.js            # AdminAPI
│   ├── tags.js             # TagsAPI
│   ├── export.js           # ExportAPI
│   ├── filters.js          # FiltersAPI
│   ├── shelloneliners.js   # ShellOnelinersAPI
│   ├── users.js            # UsersAPI
│   ├── relationships.js    # RelationshipsAPI
│   └── attack_maps.js      # AttackMapsAPI
├── api.js                  # Facade — imports all API modules, exports window.API
├── utils.js                # escapeHtml, showToast, openModal, debounce, formatDate
├── app.js                  # AppState, DOMContentLoaded init, switchSection, navigation
├── hosts.js                # HostManager — host list, evidence, ports, credentials
├── reporting.js            # ReportingManager — writeups, report builder, templates
├── testplans.js            # TestPlansManager — MITRE ATT&CK, Atomic Red Team
├── tools.js                # ToolsManager — MSFVenom, CVSS calc, CyberChef, subnet
├── attack_map_editor.js    # AttackMapEditor — visual attack path builder
├── relationship_graph.js   # Relationship graph visualization
├── commands.js             # CommandManager — command database CRUD
├── users.js                # UserManager — RBAC user management
├── auth.js                 # Auth UI logic
└── admin.js                # AdminPanel — backup, settings
```

---

## API Layer Architecture

### Base Request Handler (`lib/request.js`)

Singleton `apiRequest` handles all HTTP communication:

```javascript
import { apiRequest } from '../lib/request.js';

// Methods: get, post, put, delete, upload
// Auto-handles: JSON serialization, content-type, error throwing, blob detection
apiRequest.get('/hosts');                        // GET /api/hosts
apiRequest.post('/hosts', { ip: '10.0.0.1' });  // POST with JSON body
apiRequest.put('/hosts/42', { os: 'Linux' });    // PUT with JSON body
apiRequest.delete('/hosts/42');                   // DELETE
apiRequest.upload('/evidence', formData);         // POST with FormData
apiRequest.get('/evidence/search', { params: { q: 'sqli' } });  // GET with query string
```

### API Module Pattern

Every API module follows this structure:

```javascript
// static/js/api/hosts.js
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

### API Facade (`api.js`)

Imports all modules and exposes `window.API` for global access:

```javascript
import { HostsAPI } from './api/hosts.js';
// ... 14 more imports

const API = {
    hosts: HostsAPI,
    engagements: EngagementsAPI,
    evidence: EvidenceAPI,
    // ... all modules
};

window.API = API;
export default API;
```

Usage: `API.hosts.getAll()` — works in any file without imports.

---

## Manager Module Pattern

Every feature section uses this structure:

```javascript
const FeatureManager = {
    // --- State ---
    initialized: false,
    items: [],
    filters: { category: 'all', search: '' },

    // --- Lifecycle ---
    async init() {
        if (this.initialized) return;  // Idempotent
        await this.loadItems();
        this.render();
        this.setupEventListeners();
        this.initialized = true;
    },

    // --- Data Loading ---
    async loadItems() {
        try {
            this.items = await API.feature.getAll();
        } catch (error) {
            console.error('Failed to load:', error);
            this.items = [];
        }
    },

    // --- Rendering ---
    render() {
        const container = document.getElementById('featureContainer');
        if (!container) return;
        container.innerHTML = this.items.map(item => `
            <div class="item">${escapeHtml(item.name)}</div>
        `).join('');
    },

    // --- Event Setup ---
    setupEventListeners() {
        // Bind events to static elements
    }
};
```

Key conventions:
- `initialized` flag prevents double-init
- `init()` called lazily from `switchSection()` in `app.js`
- State lives directly on the object (no nesting)
- `render()` does full innerHTML replacement
- Error handlers set empty state and still re-render

---

## Inter-Module Communication

### Global State (AppState)

```javascript
// app.js writes
AppState.activeEngagement = engagement;

// hosts.js reads
if (AppState.activeEngagement) {
    await this.loadHosts();
}
```

### Direct Manager Calls

```javascript
// app.js triggers managers
await HostManager.init();
await HostManager.loadHosts();

// After data mutation, refresh dependent modules
await HostManager.loadHosts();
await refreshEvidenceStats();
await refreshEngagementCardStats(AppState.activeEngagement.id);
```

### Global Functions via window

```javascript
// app.js exposes handlers for inline onclick
window.handleEditEngagement = handleEditEngagement;
window.switchSection = switchSection;
window.exportData = exportData;
```

### WARNING: Circular Refresh Loops

**The Problem:**

```javascript
// BAD - Module A refreshes B, B refreshes A → infinite loop
HostManager.onUpdate = () => AppState.refresh();
AppState.refresh = () => HostManager.loadHosts();
```

**The Fix:**

Keep refresh chains unidirectional. After an API mutation:
1. Reload the affected manager's data
2. Re-render
3. Update dependent stats (one-way only)

---

## Module Loading Order

In `dashboard.html`, scripts load in dependency order:

```html
<!-- Utilities first (no dependencies) -->
<script src="/static/js/utils.js"></script>

<!-- API layer (depends on lib/request.js, loaded as module) -->
<script type="module" src="/static/js/api.js"></script>

<!-- Feature modules (depend on utils.js and API) -->
<script src="/static/js/hosts.js"></script>
<script src="/static/js/reporting.js"></script>
<script src="/static/js/testplans.js"></script>
<script src="/static/js/tools.js"></script>
<script src="/static/js/commands.js"></script>
<script src="/static/js/users.js"></script>
<script src="/static/js/admin.js"></script>
<script src="/static/js/attack_map_editor.js"></script>

<!-- App core last (depends on everything above) -->
<script src="/static/js/app.js"></script>
```

---

## Adding a New Feature

Copy this checklist and track progress:
- [ ] Step 1: Create API module in `static/js/api/newfeature.js`
- [ ] Step 2: Import and register in `static/js/api.js`
- [ ] Step 3: Create Manager in `static/js/newfeature.js`
- [ ] Step 4: Add `<script>` tag in `dashboard.html` (before `app.js`)
- [ ] Step 5: Add section HTML in `dashboard.html`: `<div id="section-newfeature" class="app-section">`
- [ ] Step 6: Add nav tab in `dashboard.html`
- [ ] Step 7: Register lazy init in `switchSection()` in `app.js`
- [ ] Step 8: Create Flask Blueprint — see the **flask** skill
- [ ] Step 9: Add migration if DB changes — see the **sqlite** skill

### 1. Create API Module

```javascript
// static/js/api/newfeature.js
import { apiRequest } from '../lib/request.js';

export const NewFeatureAPI = {
    async getAll() {
        return apiRequest.get('/newfeature');
    },
    async create(data) {
        return apiRequest.post('/newfeature', data);
    },
    async update(id, data) {
        return apiRequest.put(`/newfeature/${id}`, data);
    },
    async delete(id) {
        return apiRequest.delete(`/newfeature/${id}`);
    }
};
```

### 2. Register in API Facade

```javascript
// static/js/api.js — add import and register
import { NewFeatureAPI } from './api/newfeature.js';

const API = {
    // ... existing modules
    newFeature: NewFeatureAPI
};
```

### 3. Register in switchSection

```javascript
// static/js/app.js
if (sectionId === 'newfeature') {
    if (typeof NewFeatureManager !== 'undefined' && !NewFeatureManager.initialized) {
        NewFeatureManager.init();
    }
}
```

### Validation Loop

1. Start dev server: `python app.py`
2. Open browser to http://localhost:5001
3. Check console for JavaScript errors
4. Click the new nav tab to trigger lazy init
5. Verify API calls succeed in Network tab
6. If errors, fix and refresh — repeat until clean

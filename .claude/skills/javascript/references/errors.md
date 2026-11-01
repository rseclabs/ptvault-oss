# JavaScript Error Handling Reference

## Contents
- Error Flow Architecture
- Standard Patterns
- User Feedback System
- Common Errors and Fixes
- Debugging Techniques

---

## Error Flow Architecture

PTVault errors flow through three layers:

1. **`apiRequest.handleResponse()`** — throws `Error` if `response.ok === false`, extracting the Flask `{"error": "..."}` message
2. **Manager/handler `try-catch`** — catches the Error, logs to console, shows toast
3. **UI recovery** — sets empty state, re-renders to avoid broken layout

```
Flask returns 400 {"error": "IP required"}
  → apiRequest throws new Error("IP required")
    → catch block calls showToast("IP required", "error")
      → Manager sets this.hosts = [] and calls this.renderHostList()
```

---

## Standard Patterns

### Data Loading with Graceful Fallback

```javascript
async loadHosts() {
    try {
        const data = await API.hosts.getAll();
        this.hosts = data.hosts || [];
        this.renderHostList();
    } catch (error) {
        console.error('Failed to load hosts:', error);
        showToast('Failed to load hosts', 'error');
        this.hosts = [];
        this.renderHostList();  // Render empty state, not broken page
    }
}
```

### Form Submission with Button State

ALWAYS disable the submit button and show loading text during async operations:

```javascript
async function handleSubmit(e) {
    e.preventDefault();
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;

    try {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';

        await API.hosts.create(data);
        closeModal('hostModal');
        await HostManager.loadHosts();
        showToast('Host created', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}
```

### Destructive Operations with Confirmation

```javascript
async deleteHost(id) {
    if (!confirm('Delete this host and all associated evidence?')) return;

    try {
        await API.hosts.delete(id);
        this.selectedHostId = null;
        await this.loadHosts();
        showToast('Host deleted', 'success');
    } catch (error) {
        showToast('Failed to delete: ' + error.message, 'error');
    }
}
```

### Input Validation Before API Call

```javascript
async function createHost(data) {
    if (!data.ip) {
        showToast('IP address required', 'warning');
        return;
    }

    if (!AppState.activeEngagement) {
        showToast('No active engagement', 'warning');
        return;
    }

    try {
        await API.hosts.create(data);
        await HostManager.loadHosts();
        showToast('Host created', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}
```

---

## User Feedback System

### Toast Types

```javascript
showToast('Evidence saved successfully', 'success');  // Green
showToast('Failed to save: ' + error.message, 'error');  // Red
showToast('Please select an engagement first', 'warning');  // Yellow
showToast('Loading data...', 'info');  // Blue
```

Default duration: 3000ms. Toasts stack vertically and auto-dismiss.

### Modal Error Display

```javascript
function showModalError(modalId, message) {
    const modal = document.getElementById(modalId);
    const errorEl = modal?.querySelector('.error-message');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }
}

function clearModalError(modalId) {
    const modal = document.getElementById(modalId);
    const errorEl = modal?.querySelector('.error-message');
    if (errorEl) {
        errorEl.style.display = 'none';
        errorEl.textContent = '';
    }
}
```

---

## WARNING: Silent API Failures

**The Problem:**

```javascript
// BAD - No error handling, user sees nothing when it fails
async function deleteHost(id) {
    await API.hosts.delete(id);
    await this.loadHosts();
}
```

**Why This Breaks:**
1. User clicks delete, nothing visible happens on failure
2. Console shows error but user sees stale UI with the host still listed
3. User retries, potentially causing duplicate operations

**The Fix:**

```javascript
// GOOD - Every API call wrapped in try-catch with feedback
async function deleteHost(id) {
    if (!confirm('Delete this host?')) return;
    try {
        await API.hosts.delete(id);
        this.selectedHostId = null;
        await this.loadHosts();
        showToast('Host deleted', 'success');
    } catch (error) {
        showToast('Failed to delete: ' + error.message, 'error');
    }
}
```

**When You Might Be Tempted:**
On "fire-and-forget" operations like updating indicators. Even these need error handling — a failed indicator update with no feedback is confusing.

---

## Common Errors and Fixes

### "Cannot read properties of null"

**Cause:** `document.getElementById()` returned null — element doesn't exist or hasn't loaded.

```javascript
// BAD
document.getElementById('missing').textContent = 'test';

// GOOD - Guard clause
const el = document.getElementById('missing');
if (!el) return;
el.textContent = 'test';
```

### "Unexpected token" in JSON.parse

**Cause:** Server returned HTML (error page or redirect) instead of JSON. Common when session expired.

The `apiRequest` handles this automatically by checking content-type. If you're calling `JSON.parse()` manually on metadata:

```javascript
// BAD
const meta = JSON.parse(evidence.metadata);

// GOOD - Handle null/invalid JSON
const meta = evidence.metadata ? JSON.parse(evidence.metadata) : {};
```

### "Failed to fetch"

**Cause:** Network error, server not running, or CORS issue.

```javascript
try {
    await API.hosts.getAll();
} catch (error) {
    if (error.message === 'Failed to fetch') {
        showToast('Cannot connect to server', 'error');
    } else {
        showToast(error.message, 'error');
    }
}
```

### State Not Updating After API Call

**Cause:** API mutation succeeded but UI wasn't re-rendered.

```javascript
// BAD - Data changed server-side, UI shows stale state
await API.hosts.update(id, data);

// GOOD - Re-fetch and re-render
await API.hosts.update(id, data);
await HostManager.loadHosts();
```

### Lucide Icons Missing After Render

**Cause:** innerHTML replacement destroyed existing Lucide icon elements.

```javascript
// REQUIRED after any innerHTML replacement that includes Lucide icons
if (typeof lucide !== 'undefined') {
    lucide.createIcons();
}
```

---

## Debugging Techniques

### Browser DevTools Network Tab

1. Open DevTools (F12) → Network tab
2. Filter by "Fetch/XHR"
3. Click a request to inspect:
   - **Headers**: Verify Content-Type and cookies
   - **Payload**: Verify request body
   - **Response**: See exact server response
   - **Status**: 401 = auth expired, 400 = bad input, 500 = server error

### Console Breakpoints

```javascript
// Temporary — add to investigate state
async loadHosts() {
    debugger;  // Pauses in DevTools, inspect this.hosts etc.
    const data = await API.hosts.getAll();
}
```

### Checking API Module Availability

When a Manager can't find `API.feature`, it's usually a loading order issue:

```javascript
// Debug: verify API is populated
console.log('API keys:', Object.keys(API));
console.log('API.hosts:', API.hosts);
```

Check that `api.js` loads as `type="module"` and the API module is imported there.

### Session Expiry Detection

If all API calls suddenly return 401:

```javascript
// apiRequest handles this — check if redirect to login happens
// If not, the JWT cookie has expired. User needs to re-login.
// The Flask middleware returns {"error": "..."} with 401 status.
```

---

## Error Recovery Patterns

### Graceful Init Failure

```javascript
async init() {
    try {
        await this.loadHosts();
    } catch (error) {
        console.error('Init failed:', error);
        this.hosts = [];
        this.renderHostList();  // Show empty state, app still usable
    }
}
```

### Parallel Load with Individual Failure Handling

```javascript
// Each load has its own try-catch — one failure doesn't block others
const [notes, ports, creds] = await Promise.allSettled([
    this.loadNotes(hostId),
    this.loadPorts(hostId),
    this.loadCredentials(hostId)
]);

// Check results individually
if (notes.status === 'rejected') {
    console.error('Notes failed:', notes.reason);
}
```

Note: The codebase currently uses `Promise.all()` — if one fails, all fail. `Promise.allSettled()` is the resilient alternative for independent loads.

# Searching & Filtering Evidence

PTVault provides powerful search and filtering capabilities to find evidence quickly, even in large engagements.

## Full-Text Search

The **search bar** uses SQLite FTS4 (Full-Text Search) to search across all evidence in the active engagement.

### How to Search

1. Click the search bar or press `Ctrl+F`
2. Type your search query
3. Results update in real time

### What is Searched

| Field | Notes |
|-------|-------|
| Evidence **title** | Exact and partial word matches |
| Evidence **content** | Full-text indexed |
| Evidence **tags** | Tag values |
| Evidence **metadata** | JSON fields including tool output |

The search uses word-boundary matching, so `sql` matches `SQL injection` and `SQLi`.

---

## Basic Filtering

Use the filter controls above the evidence list to narrow results:

| Filter | Options |
|--------|---------|
| **Type** | Note, Screenshot, Command Output, Tool Output, Other |
| **Host** | Filter to a specific host's evidence |
| **Tags** | Enter a tag to filter to matching items |

---

## Advanced Filtering

Click **Advanced Filter** (or the filter icon) to access the full filter panel:

| Filter Parameter | Description |
|------------------|-------------|
| **Search Query** | Full-text search string |
| **Tags** | Multiple tags (AND logic — all tags must be present) |
| **Evidence Type** | Filter by type |
| **Severity Level** | `critical`, `high`, `medium`, `low`, `info` |
| **Tool Name** | Filter by tool that generated the evidence |
| **Host** | Filter to a specific host |
| **Host Indicators** | Filter by host status indicators |
| **CIDR Range** | Filter evidence linked to hosts in a CIDR range (e.g., `192.168.1.0/24`) |
| **Date Range** | Filter by creation date |

### Tag Logic

- **Basic tag filter**: Single tag — shows evidence tagged with that value
- **Advanced tag filter**: Multiple tags — shows evidence that has **all** specified tags (AND logic)

---

## Saved Filters

Complex filter configurations can be saved and reused across sessions.

### Saving a Filter

1. Configure your desired filters in the Advanced Filter panel
2. Click **Save Filter**
3. Enter a name for the filter (e.g., `Critical Findings - Web`)
4. Click **Save**

### Loading a Saved Filter

1. Click the **Saved Filters** dropdown
2. Select the filter by name
3. The filters are applied automatically

### Managing Saved Filters

- Click **Edit** next to a saved filter to update its parameters
- Click **Delete** to remove a filter you no longer need

Saved filters are scoped to the **active engagement** — they are not shared across engagements.

---

## Host-Level Search

In addition to the evidence-level search, the **host list search bar** searches across host data including:
- IP addresses and hostnames
- Evidence linked to each host
- Port numbers and service names
- Credential usernames
- Nested tool scan data (e.g., Nessus vulnerability descriptions and CVEs)

This is useful for questions like "which hosts have port 3389 open?" or "which hosts have Nessus findings related to PrintNightmare?"

---

## Search Tips

| Goal | Search Strategy |
|------|-----------------|
| Find all SQL injection findings | Search `sql injection` + tag filter `critical` |
| Find all Nmap data | Filter by Tool Name = `nmap` |
| Find hosts in a subnet | Use CIDR filter `10.10.10.0/24` |
| Find recent critical items | Filter by Severity = `critical` + Date Range = last 7 days |
| Find untagged evidence | Search and sort by tag count |

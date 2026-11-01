# Quick Start Workflow

This guide walks through a complete, typical penetration testing workflow in PTVault from start to finish.

## Overview

```
Create Engagement → Add Hosts → Collect Evidence → Document Findings → Generate Report
```

---

## 1. Create an Engagement

Every piece of data in PTVault belongs to an engagement (client project).

1. Click **Engagements** in the top navigation
2. Click **+ New Engagement**
3. Fill in:
   - **Name**: e.g., `ACME Corp External Pentest`
   - **Client Name**: `ACME Corporation`
   - **Start / End Dates**: Your engagement timeline
   - **Status**: `Active`
4. Click **Create**
5. Click the engagement card to make it your **active engagement**

> All subsequent actions apply to the active engagement shown in the header.

---

## 2. Import Nmap Scan Results

Rather than adding hosts manually, import your Nmap XML output directly.

1. Click the **Hosts** tab
2. Click **Import** (or use the evidence import in the sidebar)
3. Select **Nmap XML** as the tool type
4. Choose your `.xml` scan file
5. PTVault automatically creates hosts and populates open ports

Alternatively, click **+ Add Host** to enter an IP address manually.

---

## 3. Set Host Indicators

After your initial reconnaissance, mark hosts to track your progress:

1. Click a host in the host list
2. Click the **Indicators** tab
3. Check appropriate indicators:
   - **Interested** — worth investigating further
   - **Out of Scope** — do not test
   - **Shell** — user-level access obtained
   - **Rooted** — full administrative access
4. Assign a **color category** to organize by network segment or priority

See [Host Indicators](../hosts/host-indicators.md) for the full indicator reference.

---

## 4. Add Evidence

Capture your findings as you work:

1. Select a host from the host list
2. Click **+ Add Evidence** (or use `Ctrl+N` for quick capture)
3. Choose the evidence type:
   - **Note** — text observations
   - **Command Output** — paste terminal output
   - **Screenshot** — upload an image file
4. Add descriptive tags: `critical`, `sql-injection`, `authentication-bypass`
5. Click **Save**

Use the **General** section for engagement-level evidence not tied to a specific host.

---

## 5. Document Credentials

When you discover credentials:

1. Select the relevant host
2. Click the **Credentials** tab
3. Click **+ Add Credential**
4. Enter: username, password (or hash), service, and notes
5. Click **Save**

---

## 6. Check the Port Grid

Get a birds-eye view of the network:

1. Click the **Port Grid** tab
2. Rows show hosts, columns show unique ports
3. Green = open, Orange = filtered

This is useful for spotting common services (RDP on multiple hosts, unusual open ports) and planning lateral movement.

---

## 7. Build a Report

1. Click the **Reporting** tab
2. Click **Writeups** to create vulnerability documentation entries
3. Switch to **Reports** and click **+ New Report**
4. Enter a report name
5. **Drag items** from the left panel (findings, writeups, format tools) into the workspace
6. Arrange items in order; edit each item as needed
7. Preview updates in real-time in the right panel
8. Click **Save**
9. Click **Export** and choose your format: HTML, PDF, Word, or Markdown

See [Report Builder](../reporting/report-builder.md) for detailed instructions.

---

## 8. Plan Testing with MITRE ATT&CK

1. Click the **Test Plans** tab
2. **Import a Navigator Layer** to define your testing scope
3. **Download Atomics** to access the Atomic Red Team library
4. Search for specific techniques and add them to a test plan
5. Track execution status (pending → running → passed/failed) as you work

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New evidence (quick capture) |
| `Ctrl+F` | Focus the search bar |
| `Ctrl+E` | Open the export dialog |
| `Esc` | Close the active modal or dialog |

---

## Next Steps

- [Engagements](../engagements/README.md) — Full engagement management guide
- [Evidence](../evidence/README.md) — Advanced evidence collection and search
- [Reporting](../reporting/README.md) — Build professional client reports

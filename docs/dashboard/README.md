# Dashboard

The Dashboard tab provides a visual summary of the active engagement's data. It uses D3 v7 charts to surface key metrics at a glance so you can track progress and coverage without navigating across multiple tabs.

---

## Accessing the Dashboard

Click the **Dashboard** tab in the top navigation bar.

If no engagement is active, the Dashboard displays an empty state. Select an active engagement first — click any engagement card in the **Engagements** tab.

---

## KPI Cards

The top row of the Dashboard shows key performance indicator cards for the active engagement:

| Card | What It Shows |
|------|--------------|
| **Hosts** | Total number of hosts tracked |
| **Open Ports** | Total open port entries across all hosts |
| **Credentials** | Total credentials discovered |
| **Findings** | Total findings (vulnerabilities) documented |

---

## Charts

### Severity Breakdown

A donut or bar chart showing the distribution of findings by severity level (Critical, High, Medium, Low, Info). Use this to communicate overall risk posture to stakeholders at a glance.

### Scan Vulnerabilities

A chart of vulnerabilities imported from scanner tool output (Nessus, Qualys, InsightVM, etc.), broken down by severity. Reflects parsed tool imports rather than manually entered findings.

### Top Ports

A horizontal bar chart of the most frequently observed open ports across all hosts. Useful for identifying common attack surface patterns (e.g., widespread SMB or RDP exposure).

### Host Status

A breakdown of hosts by their indicator status (Rooted, Shell, Interested, Not Interested, Out of Scope, Flagged, Reviewed). Shows testing progress at a glance.

### Findings Over Time

A line or area chart plotting when findings were added to the engagement. Useful for tracking documentation cadence across a multi-day engagement.

### Color Categories

A breakdown of hosts by their assigned color category. Reflects however your team uses colors — for example, network segments, priority tiers, or asset types.

### Test Execution Summary

A summary of test plan execution status (if test plans are in use): how many atomics have been executed, how many are pending, and how many passed or failed.

---

## Refresh

Click the **Refresh** button to reload all chart data from the database. The timestamp next to the button shows when the data was last loaded.

> **Note:** The Dashboard does not auto-refresh. Click Refresh manually after adding hosts, findings, or running imports to update the charts.

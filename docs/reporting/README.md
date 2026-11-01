# Reporting

The Reporting section lets you build professional penetration testing reports using a drag-and-drop interface and a reusable library of vulnerability writeups.

## In This Section

- [Writeups Database](./writeups-database.md) — Create and manage reusable vulnerability documentation
- [Report Builder](./report-builder.md) — Assemble reports with drag-and-drop
- [Format Tools Reference](./format-tools.md) — All 20 format tools explained
- [Exporting Reports](./exporting-reports.md) — HTML, PDF, Word, and Markdown export

## How Reporting Works

PTVault's reporting system has two components:

### 1. Writeups Database
A library of **reusable vulnerability documentation** stored globally across all engagements. Write a finding once (e.g., "SQL Injection") with description and remediation guidance, then reuse it across multiple client reports.

Two writeup types:
- **Finding**: Technical vulnerability documentation with severity, CVSS, description, and remediation
- **Narrative**: Executive summaries, methodology sections, scope statements, and other report prose

### 2. Report Builder
A **drag-and-drop workspace** where you assemble a report from:
- Engagement-specific findings
- Writeups from the library
- Format tools (headers, tables, timelines, code blocks, etc.)

The report builder has three panels:
- **Left**: Source items (findingss, writeups, format tools)
- **Center**: The report workspace (drag items here to build structure)
- **Right**: Live HTML preview

## Workflow

1. **Build your writeups library** with common vulnerability types and executive narrative templates
2. During an engagement, **create engagement-specific findings** with client-specific evidence
3. **Assemble a report** by dragging writeups, findings, and format tools into the workspace
4. **Export** as HTML, PDF, Word, or Markdown

## Auto-Population

The **Auto-Populate** feature scans the active engagement for evidence items tagged as findings and automatically adds them to the report workspace, saving time on initial report assembly.

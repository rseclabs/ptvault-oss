# Report Builder

The Report Builder is a drag-and-drop workspace for assembling professional penetration testing reports.

## Interface Overview

The report builder uses a three-panel layout:

| Panel | Purpose |
|-------|---------|
| **Left (Available Items)** | Source content: engagement findings, writeups library, format tools |
| **Center (Workspace)** | Your report structure — drag items here to build the document |
| **Right (Live Preview)** | Real-time HTML rendering of the assembled report |

---

## Creating a New Report

1. Click the **Reporting** tab
2. Click **Reports** in the sub-navigation
3. Click **+ New Report**
4. Enter a **report name** (e.g., `ACME Corp External Pentest - Draft`)
5. The workspace loads empty and ready for content

---

## Adding Content to the Report

### From Available Items (Left Panel)

Three content sources are available:

**Engagement Findings**
Evidence items from the current engagement tagged as findings or vulnerabilities. Drag any item into the workspace.

**Writeups Database**
Reusable vulnerability documentation from your library. Search and filter by name, category, or criticality. Drag into the workspace.

**Format Tools**
20 structural and visual elements. Click a tool to add it to the workspace, or drag it to a specific position.

### Placing Items

- **Drag** any item from the left panel into the workspace
- Items are inserted at the position you drop them
- Drag items within the workspace to **reorder** them

---

## Editing Items in the Workspace

Each item in the workspace has an **edit icon** (pencil). Click it to open the item's editor:

- **Finding / Writeup**: Edit title, severity, description, and remediation for this specific report (changes do not affect the library original)
- **Format tools**: Each tool has its own editor appropriate to its content (see [Format Tools Reference](./format-tools.md))

---

## Reordering Items

Drag items within the workspace to change their order. Items can be dragged to any position relative to other items.

---

## Removing Items

Click the **delete icon** (X) on any workspace item to remove it from the report. This does not delete the source writeup or evidence item.

---

## Saving the Report

Click **Save** to save the current workspace state. Reports auto-save the content as a JSON structure representing the workspace items and their settings.

You can have **multiple reports** per engagement (e.g., Technical Report and Executive Summary).

---

## Loading an Existing Report

1. Click the **report selector** dropdown at the top of the Reporting section
2. Select an existing report by name
3. The workspace loads with all previously saved items

---

## Auto-Populate

The **Auto-Populate** button scans the active engagement and automatically adds found evidence items to the workspace based on their type and severity.

1. Create or open a report
2. Click **Auto-Populate**
3. PTVault adds engagement findings to the workspace in severity order (Critical → High → Medium → Low)
4. Review and reorder as needed

This is useful as a starting point when you have many evidence items and want to quickly get a populated draft.

---

## Live Preview

The right panel shows a real-time HTML preview of your report. The preview updates as you:
- Add or remove items
- Edit item content
- Reorder items

The preview renders Markdown in text fields, applies severity color coding to findings, and shows format tools (tables, timelines, code blocks, etc.) as they will appear in exports.

---

## Report Naming and Management

| Action | How |
|--------|-----|
| Rename a report | Edit the report name field at the top and save |
| Delete a report | Use the report options menu → Delete |
| Duplicate a report | Not currently supported — save as new report name |

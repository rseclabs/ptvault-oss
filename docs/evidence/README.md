# Evidence

Evidence items are the core data objects in PTVault. Every artifact you collect during a penetration test — notes, screenshots, command output, tool results — is stored as an evidence item.

## In This Section

- [Collecting Evidence](./collecting-evidence.md) — Create and manage evidence items
- [File Uploads & Tool Imports](./file-uploads.md) — Upload files and auto-parse tool output
- [Searching & Filtering](./searching-filtering.md) — Find evidence with full-text search and saved filters
- [Bulk Operations](./bulk-operations.md) — Tag, move, export, or delete multiple items at once

## Evidence Types

| Type | Description |
|------|-------------|
| **Note** | Text observations, vulnerability descriptions, methodology notes |
| **Screenshot** | Image files (PNG, JPG, JPEG) serving as visual evidence |
| **Command Output** | Terminal/console output captured during testing |
| **Tool Output** | Parsed results automatically extracted from security tool exports |
| **Other** | Miscellaneous files (PDFs, logs, PCAPs, etc.) |

## How Evidence is Organized

Evidence is associated with:
- **A specific host**: Shown when that host is selected in the host list
- **The General section**: Engagement-level evidence not tied to a specific host

## Tags

Every evidence item can have one or more **tags** — short labels used for categorization and filtering. Examples: `critical`, `sql-injection`, `nmap`, `authentication-bypass`.

Tags support autocomplete suggestions based on tags already used in your engagement.

## Quick Reference

| Task | How |
|------|-----|
| Add a note | Click **+ Add Evidence**, select **Note** |
| Upload a screenshot | Click **+ Add Evidence**, select **Screenshot**, attach file |
| Import Nmap results | Upload an Nmap XML file → auto-parsed |
| Search evidence | Use the search bar or `Ctrl+F` |
| Filter by tag | Use the filter panel |
| Bulk delete | Select items → Bulk Actions → Delete |

# Exporting & Importing Engagements

PTVault supports exporting engagement data for backup, sharing, or archiving, and importing previously exported data.

## Exporting an Engagement

### JSON Export

Exports the complete engagement data as a structured JSON file, including all hosts, evidence (metadata and file references), credentials, ports, and notes.

1. Open the engagement (make it active)
2. Click the **Export** button (or the export icon on the engagement card)
3. Select **JSON**
4. The download starts automatically

The JSON export includes:
- Engagement metadata (name, client, dates, status, tags)
- All hosts with their indicators, ports, and credentials
- All evidence items with metadata (file content is referenced by path, not embedded)
- All host notes
- Summary statistics

**Use case:** Backup, archiving, transferring data to another PTVault instance.

### Markdown Export

Exports the engagement as a formatted Markdown document suitable for manual review.

1. Click **Export** → **Markdown**
2. The `.md` file downloads automatically

### Template Export

If you have custom Jinja2 report templates, you can export engagement data using any installed template:

1. Click **Export** → **Template**
2. Select a template from the dropdown
3. The rendered output downloads automatically

Built-in templates include:
- `default` — Standard penetration test report structure
- `executive` — Executive summary-focused format

See [Reporting](../reporting/README.md) for creating custom report templates.

---

## Importing an Engagement

Previously exported JSON data can be imported to create a new engagement with all its data intact.

1. Click **+ Import Engagement** on the Engagements tab
2. Select the `.json` export file
3. PTVault creates a new engagement with all data from the file
4. Review the imported data

> **Note:** File attachments (screenshots, uploaded files) are referenced by path in the export and must be available at those paths for download to work correctly after import. Evidence metadata is always imported regardless of file availability.

---

## What is Included in Exports

| Data | JSON | Markdown |
|------|:----:|:--------:|
| Engagement metadata | ✓ | ✓ |
| Hosts and IP addresses | ✓ | ✓ |
| Host indicators and colors | ✓ | — |
| Open ports | ✓ | ✓ |
| Credentials | ✓ | ✓ |
| Host notes | ✓ | ✓ |
| Evidence titles and content | ✓ | ✓ |
| Evidence file attachments | Reference only | — |
| Evidence tags | ✓ | ✓ |
| Evidence metadata | ✓ | — |
| Summary statistics | ✓ | ✓ |

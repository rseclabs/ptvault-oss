# Exporting Reports

Once your report is assembled in the workspace, export it in one of four formats for delivery to the client.

## Export Formats

| Format | Description | Best For |
|--------|-------------|---------|
| **HTML** | Standalone HTML file with embedded styles | Sharing digitally, web publishing |
| **PDF** | Formatted PDF via WeasyPrint | Professional delivery, printing |
| **Word (DOCX)** | Microsoft Word document | Clients who need editable reports |
| **Markdown** | Plain text Markdown | Developer-friendly format, version control |

## Exporting

1. Open the report in the Report Builder
2. Click the **Export** button
3. Select your desired format
4. The file downloads to your browser's default download location

---

## HTML Export

Generates a single `.html` file with all styles embedded inline. The file:
- Requires no internet connection to view (styles are self-contained)
- Renders consistently across browsers
- Preserves all formatting: syntax highlighting, color badges, tables, timelines

**Best for:** Sharing via email or a file share when the client needs a clean, read-only view.

---

## PDF Export

Generates a PDF server-side using **WeasyPrint**. The PDF:
- Respects page breaks inserted with the Page Break format tool
- Preserves colors and styling
- Includes vector-based text (searchable and copyable)

**Requirements:** WeasyPrint must be installed (`pip install weasyprint`). Some Linux distributions also require system font packages.

**Alternative:** If WeasyPrint is not available, clicking PDF in the UI may open a browser print dialog. Use your browser's "Save as PDF" option.

---

## Word (DOCX) Export

Generates a Microsoft Word `.docx` file using **python-docx**. The document:
- Uses standard Word paragraph and heading styles
- Preserves tables and code blocks
- Can be edited by clients for customization

**Note:** Complex formatting (syntax highlighting, custom colors) may be simplified in the Word output compared to HTML.

---

## Markdown Export

Generates a `.md` file with the report content in plain Markdown. This format:
- Works with any Markdown editor or viewer
- Can be committed to a Git repository
- Is human-readable in plain text

---

## Export via Engagement Export

You can also export engagement data using Jinja2 templates directly from the Engagements section. This is separate from the Report Builder and generates a structured report from raw engagement data (not the custom workspace layout).

Available templates:
- `default` — Standard penetration test structure
- `executive` — Executive summary format

To use: Go to Engagements → select engagement → Export → Template → choose template.

---

## Tips

- Before exporting to PDF, use the **Live Preview** to verify the layout looks correct
- Add **Page Break** format tools between major sections for clean PDF pagination
- For Word exports, plan for some manual formatting adjustments to match your firm's template
- The HTML export is the highest-fidelity output — use it as the master reference

# Format Tools Reference

Format tools are structural and visual elements you can add to a report workspace. PTVault includes 20 format tools organized into five categories.

---

## Basic Tools

### Spacer
Adds vertical whitespace between sections for visual breathing room. No editor — just adds space.

### Divider
Inserts a horizontal rule (`<hr>`) to separate major sections. No editor.

### Page Break
Marks a page break location. Displayed as a dashed indicator line in the preview; creates an actual page break in PDF and print output. No editor.

---

## Text Content Tools

### Section Header
Creates a styled heading.

**Editor options:**

| Option | Description |
|--------|-------------|
| Header Text | The heading content |
| Level | H1 (Report title), H2 (Major section), H3 (Subsection), H4 (Minor heading) |
| Numbered | Enable automatic section numbering |
| Number | Manual section number (e.g., `2.1`, `3.2.1`) |

**Typical usage:**
- H1: Report title
- H2: Executive Summary, Scope, Methodology, Findings, Recommendations
- H3: Finding categories or host sections
- H4: Sub-findings or detailed steps

### Text Block
A rich text paragraph with full Markdown support.

**Supported Markdown:** Bold, italic, inline code, fenced code blocks, links, bullet lists, numbered lists, tables, blockquotes.

**Use for:** Methodology descriptions, scope statements, custom narrative text, executive commentary.

### Quote Block
A styled blockquote with optional attribution.

**Editor options:**

| Option | Description |
|--------|-------------|
| Quote Text | The quoted content |
| Attribution | Source or speaker (optional, displayed as `— Name`) |

**Use for:** Client policy excerpts, key statements from documentation, important callouts.

---

## List Tools

### Bullet List
An unordered list with customizable items. Items can be added, removed, and reordered via drag.

**Use for:** Feature lists, affected systems, unordered recommendations.

### Numbered List
An ordered list with customizable items.

**Use for:** Step-by-step exploitation steps, prioritized recommendations, attack chain documentation.

### Checklist
A checkbox list showing checked/unchecked states.

**Editor options:**

| Option | Description |
|--------|-------------|
| Checklist Title | Header for the checklist |
| Items | Each item has text and a checked/unchecked state |

**Use for:** Remediation tracking, compliance checklists, testing coverage verification.

---

## Code & Terminal Tools

### Code Block
Syntax-highlighted code with language selection.

**Editor options:**

| Option | Description |
|--------|-------------|
| Title | Optional filename or description (e.g., `exploit.py`) |
| Language | Bash, Python, JavaScript, PowerShell, SQL, PHP, Java, C#, XML/HTML, JSON, YAML, Plain Text |
| Code | The code content |

**Use for:** Exploit proof-of-concept code, configuration snippets, vulnerable code examples.

### Command Output
A terminal-styled display showing a command and its output.

**Editor options:**

| Option | Description |
|--------|-------------|
| Command | The command that was executed (displayed with a `$` prompt) |
| Output | The resulting output |

**Preview:** Dark terminal theme with green prompt and white output text.

**Use for:** Demonstrating successful exploitation, showing enumeration results, documenting proof of access.

---

## Callout & Highlight Tools

### Alert Box
A colored callout box for important information.

**Alert types:**

| Type | Color | Icon | Best For |
|------|-------|------|----------|
| Info | Blue | ℹ | Tips, general information |
| Warning | Yellow | ⚠ | Cautions, important notes |
| Danger | Red | ⛔ | Critical warnings, security risks |
| Success | Green | ✓ | Positive outcomes, implemented fixes |

### Key Finding
A highlighted summary box for critical discoveries.

**Editor options:**

| Option | Description |
|--------|-------------|
| Title | Finding headline (e.g., `Domain Admin Compromise`) |
| Content | Brief description of impact and method |

**Use for:** Executive summary highlights, most critical vulnerabilities, key risk indicators.

### Evidence Block
Structured evidence documentation with image support.

**Editor options:**

| Option | Description |
|--------|-------------|
| Image Caption | Description of the screenshot |
| Description | Detailed explanation of what the image shows |
| Impact | Business or technical impact statement |

**Use for:** Screenshot evidence with structured context, proof-of-concept documentation.

### Image Placeholder
A placeholder for images that will be inserted later.

**Editor options:**

| Option | Description |
|--------|-------------|
| Caption | Figure caption (e.g., `Figure 1: Admin Panel Access`) |
| Width | 100% (Full), 75% (Large), 50% (Medium), 25% (Small) |

**Use for:** Reserving space for screenshots during report drafting, figure references.

---

## Data & Layout Tools

### Table
A fully customizable data table.

**Editor features:**
- Add and remove columns
- Add and remove rows
- Edit header text
- Edit each cell

**Use for:** Vulnerability summary tables, host/port matrices, comparison data, scope tables.

### Two-Column Layout
Side-by-side content columns.

**Editor options:**

| Option | Description |
|--------|-------------|
| Left Title | Left column heading |
| Left Content | Left column content (Markdown supported) |
| Right Title | Right column heading |
| Right Content | Right column content (Markdown supported) |

**Use for:** Before/After comparisons, Current State vs. Recommendations, Technical vs. Business impact.

### Timeline
A vertical timeline of sequential events.

**Editor features:**
- Add steps with a **+ Add Step** button
- Each step has: Time/Date, Title, Description

**Use for:** Attack chain documentation, incident timelines, testing phase sequences.

### Risk Matrix
A visual likelihood × impact grid.

**Editor options:**

| Option | Description |
|--------|-------------|
| Matrix Size | 3×3 (Simple) or 5×5 (Detailed) |
| Highlighted Cell | Click to mark the risk position |

**3×3 labels:** Likelihood (High/Medium/Low) × Impact (Low/Medium/High)

**5×5 labels:** Likelihood (Critical/High/Medium/Low/Info) × Impact (Rare/Unlikely/Possible/Likely/Certain)

**Use for:** Overall engagement risk visualization, individual finding context, executive summary graphics.

### CVSS Score Card
A visual CVSS score display with vector breakdown.

**Editor options:**

| Option | Description |
|--------|-------------|
| CVSS Score | Numeric score (0.0–10.0) |
| CVSS Vector | Full CVSS vector string (e.g., `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`) |

**Severity color coding:**

| Score | Severity | Color |
|-------|----------|-------|
| 0.0 | None | Gray |
| 0.1–3.9 | Low | Blue |
| 4.0–6.9 | Medium | Yellow |
| 7.0–8.9 | High | Orange |
| 9.0–10.0 | Critical | Red |

The vector string is automatically parsed to display individual metric values (AV, AC, PR, UI, S, C, I, A).

### Attack Map
Embeds a saved attack map diagram from the Attack Maps section.

**Use for:** Visualizing the attack path in a report, showing lateral movement.

Requires at least one saved attack map in the current engagement. See [Attack Maps](../tools/attack-maps.md).

# Writeups Database

The Writeups Database is a global library of reusable vulnerability documentation. Unlike engagement-specific evidence, writeups are shared across all engagements and can be pulled into any report.

## Accessing the Writeups Database

1. Click the **Reporting** tab
2. Click **Writeups** in the sub-navigation

## Writeup Types

### Finding
A technical vulnerability write-up with structured fields for severity, CVSS, description, and remediation.

**Fields:**

| Field | Description |
|-------|-------------|
| **Name** | Vulnerability title (e.g., `SQL Injection – Login Form`) |
| **Category** | Classification (e.g., `Injection`, `Authentication`, `Cryptography`) |
| **Criticality** | Critical, High, Medium, or Low |
| **CVSS Score** | Numeric score from 0.0 to 10.0 |
| **Description** | Technical description of the vulnerability (Markdown supported) |
| **Remediation** | Fix recommendations (Markdown supported) |
| **Tags** | Keywords for search and filtering (e.g., `owasp`, `web`, `sql`) |

### Narrative
Free-form prose for non-technical report sections.

**Fields:**

| Field | Description |
|-------|-------------|
| **Name** | Section title (e.g., `Executive Summary`, `Testing Methodology`) |
| **Category** | Document section type |
| **Description** | Content body (Markdown supported) |
| **Tags** | Keywords for filtering |

## Creating a Writeup

1. Click **+ New Writeup**
2. Select the type: **Finding** or **Narrative**
3. Fill in the fields
4. Click **Save**

### The Writeup Editor

The **Description** and **Remediation** fields use the **EasyMDE editor** — the same Markdown editor used in host notes. It includes a full toolbar for formatting and a live preview mode.

**Toolbar features:**
- Bold, italic, strikethrough, heading
- Unordered list, ordered list, checklist
- Inline code and fenced code blocks with syntax highlighting
- Link insertion
- Preview / side-by-side preview toggle
- Full-screen mode

To toggle between raw Markdown and rendered output, click the **Preview** button in the toolbar (eye icon), or use the **Side-by-side** button for simultaneous edit and preview.

**Supported Markdown syntax:**
- `**bold**` and `*italic*`
- Code blocks with syntax highlighting
- Bullet and numbered lists
- Tables
- Links

### Pasting Images into Writeups

You can paste screenshots directly from your clipboard into the Description or Remediation fields:

1. Copy an image to your clipboard
2. Click inside the editor field to focus it
3. Press **Ctrl+V** (Windows/Linux) or **Cmd+V** (macOS)

PTVault uploads the image automatically and inserts a Markdown image reference at the cursor position. Switch to **Preview** mode to confirm the image renders correctly.

## Editing a Writeup

1. Find the writeup in the list
2. Click the **edit icon** (pencil)
3. Modify any fields
4. Click **Save**

## Deleting a Writeup

Click the **delete icon** (trash) on a writeup and confirm.

> **Note:** Deleting a writeup from the library does not affect reports that already include it — the report workspace stores a snapshot of the content.

## Searching and Filtering Writeups

Use the filter controls at the top of the Writeups list:

| Filter | Options |
|--------|---------|
| **Search** | Text search across name, description, and tags |
| **Type** | Finding or Narrative |
| **Category** | Filter by category |
| **Criticality** | Critical, High, Medium, Low |
| **Tags** | Tag filter |

## Building a Writeups Library

### Recommended Library Structure

**Narratives:**
- Executive Summary (template)
- Testing Methodology
- Scope and Rules of Engagement
- Disclaimer / Limitations

**Findings by category:**
- Injection (SQLi, XSS, Command Injection, XXE)
- Authentication (Weak passwords, Brute force, Default creds)
- Access Control (IDOR, Privilege escalation, Path traversal)
- Cryptography (Weak TLS, Self-signed certs, Weak hashing)
- Configuration (Exposed services, Debug mode, Directory listing)
- Active Directory (Kerberoasting, AS-REP Roasting, Pass-the-hash)

### Tips

- Write **generic descriptions** in the library and add **client-specific details** in the report workspace when you drag items in
- Use **CVSS scores** in the library for reference, but override them per-engagement when the actual impact differs
- Tag writeups consistently — `owasp-top-10`, `internal`, `external`, `web`, `network` — to make filtering easy

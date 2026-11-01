# Collecting Evidence

## Adding Evidence

### Method 1: Quick Capture (`Ctrl+N`)

Press `Ctrl+N` anywhere in the application to open the quick evidence capture dialog. Enter a title and content, then save.

### Method 2: Add Evidence Button

1. Select a host in the host list (or select **General** for engagement-level evidence)
2. Click **+ Add Evidence**
3. Select the evidence type
4. Fill in the fields
5. Click **Save**

### Method 3: Paste an Image from the Clipboard

In the host notes editor or finding editor, you can paste screenshots directly from your clipboard:

1. Copy an image to your clipboard (screenshot, browser, image editor)
2. Click inside the notes/finding editor to focus it
3. Press **Ctrl+V** (Windows/Linux) or **Cmd+V** (macOS)

PTVault automatically uploads the image as an evidence file, links it to the current host, and inserts a Markdown image reference at the cursor position. See [Host Notes](../hosts/host-notes.md#pasting-images-from-the-clipboard) for full details.

---

## Evidence Fields

| Field | Required | Description |
|-------|:--------:|-------------|
| **Title** | Yes | Short descriptive name (e.g., `SQL Injection in Login Form`) |
| **Type** | Yes | Note, Screenshot, Command Output, Tool Output, Other |
| **Content** | No | Text content of the evidence item |
| **Tags** | No | Comma-separated labels for filtering (e.g., `critical,sql-injection`) |
| **File** | No | Attached file (image, XML, JSON, log, etc.) |
| **Metadata** | No | JSON field for tool-specific data (severity, CVE, CVSS, tool name) |

---

## Evidence Types in Detail

### Note
General text evidence. Use for:
- Vulnerability descriptions
- Observations during testing
- Methodology documentation
- Links and references

Content supports plain text. For Markdown rendering in reports, use the report builder's Text Block tool.

### Screenshot
Attach an image file. Supported formats: `.png`, `.jpg`, `.jpeg`.

Use for:
- Proof-of-concept screenshots
- UI evidence (admin panel access, error messages)
- Before/after comparisons

### Command Output
Paste raw terminal/console output. Use for:
- Exploit commands and their output
- Enumeration results
- Tool output that wasn't auto-parsed

### Tool Output
Upload a file from a supported security tool. PTVault auto-detects the tool type and parses the file to extract hosts, ports, and findings. Supported tools include Nmap, Nessus, Burp Suite, Nuclei, and more.

See [File Uploads & Tool Imports](./file-uploads.md) for details.

### Other
Any other file type. Use for:
- PDF documents
- PCAP captures
- Log files
- Custom reports

---

## Editing Evidence

1. Find the evidence item in the list
2. Click the **edit icon** (pencil) on the item
3. Modify the title, content, tags, or metadata
4. Click **Save**

---

## Deleting Evidence

1. Click the **delete icon** (trash) on the evidence item
2. Confirm the deletion

Deleting evidence also removes any attached file from disk. This action cannot be undone.

---

## Downloading Attached Files

Click the **download icon** on an evidence item to download its attached file with the original filename.

---

## Linking Evidence to a Host

Evidence can be linked to a host when it is created (by selecting the host first) or moved afterward using [Bulk Operations](./bulk-operations.md).

To move individual evidence to a different host:
1. Edit the evidence item
2. The host association is shown — use bulk move for reassignment

---

## Tags and Metadata

### Tags

Tags are comma-separated labels that appear on each evidence item. Examples: `critical`, `medium`, `xss`, `nmap`, `web`, `active-directory`.

When you start typing a tag, the input offers **autocomplete suggestions** based on tags already used in your engagement, sorted by frequency.

**Auto-generated tags from tool imports:** When a tool file is parsed, relevant tags are automatically applied. For example, Nmap imports add `nmap` and `port-scan`. Nessus imports with critical findings add `critical-findings`.

### Metadata

The metadata field stores structured JSON data associated with the evidence. Common metadata fields set by tool parsers:

| Key | Description |
|-----|-------------|
| `tool_name` | Tool that generated this evidence (`nmap`, `nessus`, `burp`) |
| `severity_level` | `critical`, `high`, `medium`, `low`, `info` |
| `cvss` | CVSS score as a decimal number |
| `cve` | CVE identifier(s) |
| `hosts` | Array of host objects extracted from the tool output |
| `host_id` | Integer ID of the host to auto-link this evidence to on creation |

You can also set these manually when creating notes:

```json
{
  "severity_level": "critical",
  "cvss": 9.8,
  "cve": "CVE-2023-1234"
}
```

#### Auto-Linking Evidence to a Host via `host_id`

When creating evidence via the API, set `metadata.host_id` to the integer ID of a host in the active engagement. PTVault will automatically create an `evidence_hosts` relationship, linking the evidence to that host — no separate API call required.

```json
{
  "type": "screenshot",
  "title": "Admin panel access",
  "metadata": { "host_id": 42 }
}
```

The host must belong to the active engagement; mismatched host IDs are silently ignored.

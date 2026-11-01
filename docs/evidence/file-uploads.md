# File Uploads & Tool Imports

PTVault can automatically parse output files from 11 security tools, extracting hosts, ports, and vulnerability data without manual data entry.

## Uploading a File

1. Click **+ Add Evidence**
2. Select evidence type **Tool Output** (for security tool files) or another type
3. Enter a title describing what the file contains
4. Click **Choose File** and select your file
5. Click **Save**

PTVault automatically detects supported file types and parses them. You will see a success message listing how many hosts, ports, or findings were extracted.

---

## Auto-Detection

When a file is uploaded without specifying a tool, PTVault examines the file format and validates it against each supported parser in order:

1. Nmap XML
2. Burp Suite XML
3. Nessus XML
4. OWASP ZAP XML
5. Qualys XML
6. Nuclei JSON/JSONL
7. Metasploit XML
8. Acunetix XML
9. InsightVM/Nexpose XML
10. BloodHound JSON
11. CrackMapExec logs

The first parser that successfully validates the file is used.

---

## Supported File Extensions

| Extension | Common Tool |
|-----------|-------------|
| `.xml` | Nmap, Burp Suite, Nessus, Metasploit, ZAP, Qualys, Acunetix, InsightVM |
| `.nessus` | Nessus (XML format with `.nessus` extension) |
| `.json` | Nuclei, BloodHound |
| `.txt` / `.log` | CrackMapExec, raw command output |
| `.png`, `.jpg`, `.jpeg` | Screenshots |
| `.pdf` | PDF reports |
| `.html` | HTML exports |
| `.pcap` | Network captures |

**Maximum upload size:** 250 MB

---

## What Gets Extracted

### Nmap XML
- All scanned hosts (creates host records)
- Open and filtered ports with protocol, state, service, version
- OS detection results
- Script output

### Nessus (`.nessus`)
- All scanned hosts (creates host records)
- Open ports
- Vulnerability findings with: plugin name, CVE, CVSS score, severity, description, solution
- Structured vulnerability metadata

### Burp Suite XML
- Web application findings
- Severity and confidence ratings
- Affected URLs and paths
- Request/response samples

### OWASP ZAP XML
- Web application findings
- Risk level and confidence
- Affected endpoints

### Qualys XML
- Vulnerability findings
- CVSS scores and severity levels
- Affected QIDs

### Nuclei JSON/JSONL
- Template-based findings
- Matched content and URLs
- Severity from template metadata

### Metasploit XML
- Exploited host sessions
- Module and payload details
- Loot and credential data

### Acunetix XML
- Web vulnerability findings
- CVSS scores and CVE references

### InsightVM / Nexpose XML
- Vulnerability findings
- Risk scores and CVSS
- Asset information

### BloodHound JSON
- Active Directory nodes (users, groups, computers, GPOs)
- Relationship edges (attack paths)
- Domain information

### CrackMapExec Logs
- Network shares
- Discovered credentials
- Session information

---

## Re-Parsing a File

If PTVault is updated with improved parsers, or if a file was imported before a parser was available, you can re-run parsing on an existing evidence item:

1. Find the evidence item in the list
2. Click the **re-parse icon** (if available) or use the evidence options menu
3. The file is parsed again with the latest parser version

---

## Manual vs. Automatic

| Method | Best For |
|--------|---------|
| **Automatic (file upload)** | Structured tool output files (Nmap, Nessus, Burp) |
| **Manual entry** | Individual findings, notes, observations |
| **Command Output** | Raw terminal output without a supported parser |

Even if a tool is not in the supported list, you can still store its output as a **Command Output** or **Other** evidence type for reference.

---

## Accessing Uploaded Files via API

Two endpoints serve attached evidence files:

| Endpoint | Behavior | Use For |
|----------|----------|---------|
| `GET /api/evidence/<id>/download` | Forces a file download (`Content-Disposition: attachment`) | Downloading the original file |
| `GET /api/evidence/<id>/file` | Serves inline (`Content-Disposition: inline`) | Embedding images in `<img src>` tags, previewing in browser |

Both endpoints enforce authentication and engagement isolation — you can only access evidence belonging to your active engagement.

The `/file` endpoint is used internally when pasted clipboard images are embedded in Markdown notes (`![image](/api/evidence/42/file)`).

# Tool Parsers

PTVault can automatically parse output files from 11 industry-standard security tools, eliminating manual data entry and ensuring structured, searchable data.

## In This Section

- [Nmap](./nmap.md) — Network scanner — hosts, ports, service detection
- [Burp Suite](./burp-suite.md) — Web application proxy — findings and requests
- [Nessus](./nessus.md) — Vulnerability scanner — CVEs, CVSS scores, plugin data
- [Other Supported Tools](./other-tools.md) — ZAP, Qualys, Nuclei, Metasploit, Acunetix, InsightVM, BloodHound, CrackMapExec

## Supported Tools

| Tool | File Format | Extracted Data |
|------|-------------|----------------|
| **Nmap** | XML | Hosts, ports, services, versions, OS detection |
| **Burp Suite** | XML | Web findings, severity, affected URLs |
| **Nessus** | XML / `.nessus` | Vulnerabilities, CVEs, CVSS, plugin data |
| **OWASP ZAP** | XML | Web application findings, risk levels |
| **Qualys** | XML | Vulnerability findings, QIDs |
| **Nuclei** | JSON / JSONL | Template-based findings, severity |
| **Metasploit** | XML | Sessions, exploited hosts, loot |
| **Acunetix** | XML | Web vulnerabilities, CVSS |
| **InsightVM / Nexpose** | XML | Vulnerabilities, risk scores |
| **BloodHound** | JSON | Active Directory nodes and attack paths |
| **CrackMapExec** | Log files | Credentials, shares, enumeration data |

## How Auto-Detection Works

When you upload a file without specifying a tool type, PTVault:

1. Reads the file header/structure
2. Tries each parser's `validate()` method in sequence
3. Uses the first parser that accepts the file
4. Parses and imports the data

You can also **manually specify** the tool type when uploading if auto-detection fails or you want to force a specific parser.

## Where Parsed Data Goes

| Extracted Item | Stored In |
|----------------|-----------|
| Hosts | `hosts` table — appear in the host list |
| Ports | `host_ports` table — appear in each host's Open Ports tab |
| Credentials | `host_credentials` table — appear in each host's Credentials tab |
| Findings/vulnerabilities | `evidence` table — appear as Tool Output evidence items |
| Tags | Auto-applied to the evidence item |
| Metadata | JSON metadata field on the evidence item |

## Security

All XML parsing uses **defusedxml** to prevent XXE (XML External Entity) injection attacks. Uploaded files are validated against the extension allowlist before processing.

Allowed upload extensions: `.txt`, `.xml`, `.json`, `.png`, `.jpg`, `.jpeg`, `.pdf`, `.html`, `.log`, `.pcap`, `.nessus`

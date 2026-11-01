# Other Supported Tools

In addition to Nmap, Burp Suite, and Nessus, PTVault supports automatic parsing of output from eight additional security tools.

---

## OWASP ZAP

**Format:** XML
**Use case:** DAST (Dynamic Application Security Testing) findings from the OWASP Zed Attack Proxy.

### Exporting from ZAP
1. In ZAP, go to **Report** → **Generate XML Report**
2. Save the `.xml` file

### What is Extracted
- Alert names and descriptions
- Risk level (High/Medium/Low/Informational)
- Affected URLs
- Evidence and solution text

---

## Qualys

**Format:** XML
**Use case:** Vulnerability management findings from Qualys VMDR or Web Application Scanner.

### Exporting from Qualys
1. Navigate to your scan results
2. Click **Export** and select **XML** format

### What is Extracted
- Vulnerability names and descriptions
- QID (Qualys ID)
- Severity and CVSS scores
- Affected hosts

---

## Nuclei

**Format:** JSON or JSONL
**Use case:** Fast template-based scanner findings.

### Generating Nuclei Output
```bash
# Output as JSON
nuclei -u https://target.com -json -o results.json

# Output as JSONL (one JSON object per line)
nuclei -u https://target.com -jsonl -o results.jsonl
```

### What is Extracted
- Template name and ID
- Severity (critical/high/medium/low/info)
- Matched content and extracted values
- Affected URL
- Tags from the template

---

## Metasploit

**Format:** XML (workspace export)
**Use case:** Session data and exploitation results from a Metasploit engagement.

### Exporting from Metasploit
```
msf> db_export -f xml /tmp/metasploit-export.xml
```

### What is Extracted
- Exploited hosts and sessions
- Module and payload details
- Loot and credential data

---

## Acunetix

**Format:** XML
**Use case:** Web vulnerability scanner findings.

### Exporting from Acunetix
1. Navigate to your scan report
2. Click **Generate Report** → **Developer** or **Executive** → **XML**

### What is Extracted
- Vulnerability name and type
- Severity and CVSS score
- CVE references
- Affected URLs and parameters

---

## InsightVM / Nexpose

**Format:** XML
**Use case:** Rapid7 InsightVM or Nexpose vulnerability management findings.

Also accepted as: `rapid7`, `nexpose` (tool name aliases)

### Exporting from InsightVM
1. Go to your site scan in InsightVM
2. Navigate to **Reports** → **Export**
3. Choose XML format

### What is Extracted
- Vulnerability titles and descriptions
- Risk scores and CVSS
- CVE identifiers
- Affected hosts and services

---

## BloodHound

**Format:** JSON
**Use case:** Active Directory attack path data collected with the BloodHound ingestor (SharpHound).

### Generating BloodHound Data
```bash
# Run SharpHound on a domain-joined machine
.\SharpHound.exe -c All --zipfilename bloodhound.zip
```

Extract the ZIP and upload individual JSON files (Computers, Users, Groups, GPOs, etc.).

### What is Extracted
- Domain information
- User, group, and computer node counts
- Session and relationship data
- Attack path summary statistics

---

## CrackMapExec

**Format:** Log files (text)
**Use case:** Network enumeration, credential spraying, and lateral movement results.

### Generating CrackMapExec Output
```bash
# SMB enumeration with output to file
crackmapexec smb 192.168.1.0/24 > cme-output.txt

# With credentials
crackmapexec smb 192.168.1.0/24 -u admin -p 'Password123' > cme-output.txt
```

### What is Extracted
- Host enumeration results (IP, hostname, domain, OS)
- Successful credential pairs
- SMB shares
- Session information

---

## Adding Support for New Tools

PTVault uses a plugin-style parser architecture. Custom parsers can be added in `utils/parsers/` by subclassing `BaseParser` and registering in `utils/parsers/registry.py`. See the project's developer documentation for details.

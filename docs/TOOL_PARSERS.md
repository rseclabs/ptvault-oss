# PTVault Tool Parsers

Comprehensive documentation for security tool output parsers in PTVault.

## Overview

PTVault supports automatic parsing of output files from 11 popular penetration testing and security tools. Each parser extracts structured data including hosts, vulnerabilities, credentials, and metadata for storage in the evidence database.

## Supported Tools

| Tool | Type | Formats | Parser Class |
|------|------|---------|--------------|
| **Nmap** | Network scanner | XML | `NmapToolParser` |
| **Burp Suite** | Web scanner | XML | `BurpToolParser` |
| **Nessus** | Vulnerability scanner | XML (.nessus) | `NessusToolParser` |
| **OWASP ZAP** | Web scanner | XML | `ZAPParser` |
| **Qualys** | Vulnerability scanner | XML | `QualysParser` |
| **Nuclei** | Template scanner | JSON, JSONL | `NucleiParser` |
| **Metasploit** | Exploitation framework | XML | `MetasploitParser` |
| **Acunetix** | Web scanner | XML | `AcunetixParser` |
| **InsightVM/Nexpose** | Vulnerability scanner | XML | `InsightVMParser` |
| **BloodHound** | AD attack path analyzer | JSON | `BloodHoundParser` |
| **CrackMapExec** | Network pentesting | Log files | `CrackMapExecParser` |

## Quick Start

### Auto-Detection (Recommended)

```python
from utils.parsers import detect_parser

# Automatically detect and parse
parser = detect_parser('/path/to/tool/output.xml')
if parser:
    data = parser.parse()
    print(f"Detected tool: {parser.tool_name}")
    print(f"Hosts: {len(data['hosts'])}")
    print(f"Findings: {len(data['findings'])}")
```

### Manual Selection

```python
from utils.parsers import get_parser

# Explicitly specify tool
parser = get_parser('nmap', '/path/to/nmap-scan.xml')
data = parser.parse()
```

### List Available Tools

```python
from utils.parsers import list_tools, get_tool_info

# Get list of supported tools
tools = list_tools()
print(tools)  # ['acunetix', 'bloodhound', 'burp', 'crackmapexec', ...]

# Get detailed info
info = get_tool_info()
print(info['nmap']['description'])  # Network scanner - port scanning and service detection
```

## Parser Output Format

All parsers return a standardized dictionary structure:

```python
{
    "tool": "tool_name",                # Tool identifier
    "summary": {                         # High-level statistics
        "total_hosts": 10,
        "total_vulnerabilities": 25,
        "by_severity": {
            "Critical": 2,
            "High": 5,
            "Medium": 10,
            "Low": 7,
            "Info": 1
        }
    },
    "hosts": [                           # Discovered hosts
        {
            "ip": "192.168.1.1",
            "hostname": "server01.domain.com",
            "os": "Linux 4.15",
            "source": "tool_name"
        }
    ],
    "findings": [                        # Vulnerabilities/issues
        {
            "title": "SQL Injection",
            "severity": "critical",      # Normalized: critical, high, medium, low, info
            "description": "...",
            "solution": "...",
            "cvss_score": "9.8",
            "cve": "CVE-2021-1234",
            "tool": "tool_name"
        }
    ],
    "credentials": [                     # Discovered credentials
        {
            "username": "admin",
            "password": "password123",
            "hash": "5f4dcc3b5aa765d61...",
            "service": "ssh",
            "tool": "tool_name"
        }
    ],
    "metadata": {                        # Tool-specific metadata
        "scan_date": "2024-01-01T12:00:00",
        "scan_args": "-sS -sV -O",
        ...
    }
}
```

## Tool-Specific Documentation

### Nmap Parser

**Input:** Nmap XML output (`-oX` flag)

**Example:**
```bash
nmap -sS -sV -O -oX scan.xml 192.168.1.0/24
```

**Extracts:**
- Hosts with status (up/down)
- Open ports with service detection
- OS fingerprinting
- Service versions

**Sample Output:**
```python
{
    "tool": "nmap",
    "tool_version": "7.80",
    "scan_type": "SYN Stealth Scan",
    "hosts": [
        {
            "ip": "192.168.1.10",
            "hostname": "server.local",
            "os": "Linux 4.15 (95% accuracy)",
            "open_ports": [
                {
                    "port": 22,
                    "protocol": "tcp",
                    "state": "open",
                    "service": "ssh",
                    "version": "OpenSSH 7.4"
                }
            ]
        }
    ]
}
```

---

### OWASP ZAP Parser

**Input:** ZAP XML report

**Extracts:**
- Web vulnerabilities by severity
- Affected URLs and parameters
- CWE and WASC classifications
- Solution recommendations

**Sample Output:**
```python
{
    "tool": "zap",
    "findings": [
        {
            "title": "SQL Injection",
            "severity": "high",
            "url": "http://example.com/login",
            "param": "username",
            "cwe": "89",
            "solution": "Use parameterized queries"
        }
    ]
}
```

---

### Qualys Parser

**Input:** Qualys XML scan report

**Extracts:**
- Host vulnerabilities with QID
- CVSS scores and vectors
- CVE mappings
- Exploitability ratings
- PCI compliance flags

**Sample Output:**
```python
{
    "tool": "qualys",
    "findings": [
        {
            "title": "Apache HTTP Server Multiple Vulnerabilities",
            "qid": "86823",
            "severity": "high",
            "cvss_score": "7.5",
            "cve": "CVE-2021-1234",
            "exploitability": "Exploitable"
        }
    ]
}
```

---

### Nuclei Parser

**Input:** Nuclei JSON or JSONL output

**Extracts:**
- Template-based findings
- Matched URLs
- Extracted data
- CVE/CWE classifications
- Template metadata

**Example:**
```bash
nuclei -u https://example.com -json -o nuclei.json
```

**Sample Output:**
```python
{
    "tool": "nuclei",
    "findings": [
        {
            "title": "Exposed .git Directory",
            "template_id": "git-config",
            "severity": "medium",
            "url": "https://example.com/.git/config",
            "matcher_name": "git-config-found"
        }
    ]
}
```

---

### Metasploit Parser

**Input:** Metasploit workspace XML export

**Extracts:**
- Discovered hosts and services
- Exploited vulnerabilities
- Collected credentials
- Loot/collected data

**Example:**
```bash
# In Metasploit console:
db_export -f xml /tmp/workspace.xml
```

**Sample Output:**
```python
{
    "tool": "metasploit",
    "workspace": "client_pentest",
    "credentials": [
        {
            "username": "admin",
            "password": "P@ssw0rd",
            "service": "smb",
            "port": "445"
        }
    ]
}
```

---

### Acunetix Parser

**Input:** Acunetix XML report

**Extracts:**
- Web application vulnerabilities
- Request/response evidence
- OWASP Top 10 mappings
- Impact assessments

---

### InsightVM/Nexpose Parser

**Input:** InsightVM/Nexpose XML report

**Extracts:**
- Vulnerability findings by severity
- CVSS v2/v3 scores
- Exploit availability
- PCI compliance data
- Solution/remediation steps

---

### BloodHound Parser

**Input:** BloodHound JSON export

**Extracts:**
- Active Directory computers
- User accounts (privileged/high-value)
- Group memberships
- Attack path relationships
- Privileged account findings

**Sample Output:**
```python
{
    "tool": "bloodhound",
    "summary": {
        "high_value_targets": 5
    },
    "findings": [
        {
            "title": "Privileged User Account: ADMIN@DOMAIN.COM",
            "severity": "high",
            "description": "Privileged user account with: Admin Count set, High Value target"
        }
    ]
}
```

---

### CrackMapExec Parser

**Input:** CrackMapExec log files

**Extracts:**
- Authenticated hosts
- Valid credentials
- "Pwned" systems (admin access)
- Accessible shares
- SAM/LSA/NTDS dumps

**Example:**
```bash
crackmapexec smb 192.168.1.0/24 -u admin -p password123 > cme.log
```

**Sample Output:**
```python
{
    "tool": "crackmapexec",
    "summary": {
        "pwned_hosts": 3
    },
    "credentials": [
        {
            "username": "admin",
            "password": "password123",
            "host": "192.168.1.10"
        }
    ],
    "findings": [
        {
            "title": "SAM Database Dumped on 192.168.1.10",
            "severity": "high"
        }
    ]
}
```

## Integration with Evidence System

### Importing Tool Output

```python
from routes.evidence import evidence_bp
from utils.parsers import detect_parser

# In evidence route
@evidence_bp.route('/import', methods=['POST'])
@require_auth
def import_tool_output():
    file = request.files.get('file')
    file_path = save_upload(file)

    # Auto-detect tool
    parser = detect_parser(file_path)
    if not parser:
        return jsonify({"error": "Unable to detect tool type"}), 400

    # Parse output
    data = parser.parse()

    # Import into database
    # ... (DAO operations)

    return jsonify({"imported": data['summary']}), 200
```

### Manual Tool Selection

```python
from utils.parsers import get_parser

# With explicit tool type
tool_type = request.form.get('tool_type')  # 'nmap', 'zap', etc.
parser = get_parser(tool_type, file_path)
data = parser.parse()
```

## Creating Custom Parsers

To add a new tool parser:

1. **Extend BaseToolParser:**

```python
from utils.parsers.base_parser import BaseToolParser

class MyToolParser(BaseToolParser):
    def validate(self, file_path=None):
        path = file_path or self.file_path
        # Return True if file is valid format
        return True

    def parse(self, file_path=None):
        path = file_path or self.file_path
        # Parse and return structured data
        return {
            "tool": "mytool",
            "hosts": [],
            "findings": [],
            "summary": {}
        }
```

2. **Register in registry.py:**

```python
from .mytool_parser import MyToolParser

PARSER_REGISTRY = {
    ...
    'mytool': MyToolParser,
}
```

3. **Add tests:**

```python
class TestMyToolParser:
    def test_validate(self):
        parser = MyToolParser('/path/to/test.xml')
        assert parser.validate()
```

## Best Practices

### Parser Development

1. **Use defusedxml** for XML parsing (XXE protection)
2. **Normalize severity** levels to PTVault standard
3. **Filter None values** before returning data
4. **Log errors** with appropriate detail level
5. **Handle encoding** issues (use `encoding='utf-8', errors='ignore'`)

### Error Handling

```python
try:
    parser = detect_parser(file_path)
    if not parser:
        logger.warning(f"Unable to detect tool for: {file_path}")
        return None

    data = parser.parse()
    if not data:
        logger.error(f"Parse failed for: {file_path}")
        return None

    return data
except Exception as e:
    logger.error(f"Parser error: {e}")
    return None
```

### Testing

- Create sample output files in `tests/fixtures/parsers/`
- Test validation with both valid and invalid files
- Test parsing with realistic data
- Test auto-detection
- Test edge cases (empty files, malformed data)

## Performance Considerations

- **Large files:** Parsers stream where possible
- **Memory:** XML parsers use lxml for efficiency
- **Validation:** Quick checks before full parsing
- **Caching:** Parsed data can be cached if needed

## Security Notes

- All XML parsers use `resolve_entities=False` (XXE protection)
- No code execution from parsed data
- File paths are sanitized before parsing
- Maximum file size limits enforced at upload

## Troubleshooting

### Parser Not Detected

**Problem:** `detect_parser()` returns `None`

**Solutions:**
- Check file format matches tool output
- Verify file is not corrupted
- Try manual tool selection with `get_parser()`
- Check parser validation logic

### Parse Returns None

**Problem:** `parser.parse()` returns `None`

**Solutions:**
- Check application logs for errors
- Verify tool version compatibility
- Validate XML/JSON structure
- Test with sample files from `tests/fixtures/`

### Missing Data Fields

**Problem:** Expected fields not present in output

**Solutions:**
- Some fields are optional (filtered with `filter_none()`)
- Tool output may vary by version
- Check tool-specific documentation
- Verify scan options produced expected output

## API Reference

### Functions

#### `detect_parser(file_path: str) -> Optional[BaseToolParser]`

Auto-detect parser based on file content.

**Returns:** Parser instance or None if detection fails

---

#### `get_parser(tool_name: str, file_path: str) -> BaseToolParser`

Get parser by tool name.

**Raises:** `ValueError` if tool unknown

---

#### `list_tools() -> list`

Get list of supported tool names.

---

#### `is_tool_supported(tool_name: str) -> bool`

Check if tool is supported (case-insensitive).

---

#### `get_tool_info() -> Dict`

Get detailed information about all tools.

## Examples

### Complete Import Workflow

```python
from utils.parsers import detect_parser
from models.database import get_db_connection

def import_scan_results(file_path, engagement_id):
    # Detect tool
    parser = detect_parser(file_path)
    if not parser:
        raise ValueError("Unknown tool format")

    # Parse
    data = parser.parse()
    if not data:
        raise ValueError("Parse failed")

    # Import hosts
    conn = get_db_connection()
    cursor = conn.cursor()

    for host in data['hosts']:
        cursor.execute('''
            INSERT INTO hosts (engagement_id, ip_address, hostname, os)
            VALUES (?, ?, ?, ?)
        ''', (engagement_id, host['ip'], host.get('hostname'), host.get('os')))

    # Import findings
    for finding in data['findings']:
        cursor.execute('''
            INSERT INTO evidence (engagement_id, type, title, content, metadata)
            VALUES (?, 'tool_output', ?, ?, ?)
        ''', (engagement_id, finding['title'], finding['description'],
              json.dumps(finding)))

    conn.commit()
    return data['summary']
```

## Future Enhancements

- Additional tool parsers (OpenVAS, Nikto, etc.)
- Parser plugins system
- Custom field mappings
- Batch import optimization
- Real-time parsing progress
- Parser version compatibility matrix

---

For questions or issues with parsers, see the test files in `tests/parsers/` for working examples.

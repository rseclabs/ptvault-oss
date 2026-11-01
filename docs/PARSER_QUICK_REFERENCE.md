# PTVault Parser Quick Reference

One-page reference for using security tool parsers in PTVault.

## Supported Tools

```
nmap          - Network scanner (XML)
burp          - Burp Suite web scanner (XML)
nessus        - Vulnerability scanner (XML)
zap           - OWASP ZAP web scanner (XML)
qualys        - Qualys vulnerability scanner (XML)
nuclei        - Template-based scanner (JSON/JSONL)
metasploit    - Exploitation framework (XML)
acunetix      - Acunetix web scanner (XML)
insightvm     - InsightVM/Nexpose (XML)
bloodhound    - Active Directory analyzer (JSON)
crackmapexec  - Network pentesting (Log files)
```

## Basic Usage

### Auto-Detect Tool

```python
from utils.parsers import detect_parser

parser = detect_parser('/path/to/scan.xml')
if parser:
    data = parser.parse()
    print(f"Tool: {data['tool']}")
    print(f"Hosts: {len(data['hosts'])}")
    print(f"Findings: {len(data['findings'])}")
```

### Manual Tool Selection

```python
from utils.parsers import get_parser

parser = get_parser('nmap', '/path/to/nmap-scan.xml')
data = parser.parse()
```

### Check Tool Support

```python
from utils.parsers import is_tool_supported, list_tools

if is_tool_supported('zap'):
    print("ZAP is supported")

all_tools = list_tools()
print(f"Supported tools: {', '.join(all_tools)}")
```

## Output Structure

```python
{
    "tool": "tool_name",
    "summary": {
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
    "hosts": [
        {
            "ip": "192.168.1.1",
            "hostname": "server.local",
            "os": "Linux",
            "source": "tool_name"
        }
    ],
    "findings": [
        {
            "title": "SQL Injection",
            "severity": "critical",
            "description": "...",
            "solution": "...",
            "tool": "tool_name"
        }
    ],
    "credentials": [
        {
            "username": "admin",
            "password": "password123",
            "service": "ssh",
            "tool": "tool_name"
        }
    ]
}
```

## Tool Examples

### Nmap
```bash
nmap -sS -sV -O -oX scan.xml 192.168.1.0/24
```

### Nuclei
```bash
nuclei -u https://example.com -json -o nuclei.json
```

### CrackMapExec
```bash
crackmapexec smb 192.168.1.0/24 -u admin -p password > cme.log
```

### Metasploit
```bash
# In Metasploit console:
db_export -f xml /tmp/workspace.xml
```

## Common Patterns

### Import into Database

```python
from utils.parsers import detect_parser
from models.database import get_db_connection
import json

parser = detect_parser(file_path)
data = parser.parse()

conn = get_db_connection()
cursor = conn.cursor()

# Import hosts
for host in data['hosts']:
    cursor.execute('''
        INSERT INTO hosts (engagement_id, ip_address, hostname, os)
        VALUES (?, ?, ?, ?)
    ''', (engagement_id, host['ip'], host.get('hostname'), host.get('os')))

# Import findings as evidence
for finding in data['findings']:
    cursor.execute('''
        INSERT INTO evidence (engagement_id, type, title, content, metadata)
        VALUES (?, 'tool_output', ?, ?, ?)
    ''', (engagement_id, finding['title'], finding['description'],
          json.dumps(finding)))

conn.commit()
```

### Error Handling

```python
from utils.parsers import detect_parser

try:
    parser = detect_parser(file_path)
    if not parser:
        print("Unknown tool format")
        return None

    data = parser.parse()
    if not data:
        print("Parse failed")
        return None

    return data
except Exception as e:
    print(f"Error: {e}")
    return None
```

## Severity Levels

All parsers normalize severity to:
- `critical` - Critical vulnerabilities
- `high` - High severity
- `medium` - Medium severity
- `low` - Low severity
- `info` - Informational

## Creating Custom Parsers

```python
from utils.parsers.base_parser import BaseToolParser

class MyToolParser(BaseToolParser):
    def validate(self, file_path=None):
        path = file_path or self.file_path
        # Return True if valid format
        return True

    def parse(self, file_path=None):
        path = file_path or self.file_path
        # Parse and return data
        return {
            "tool": "mytool",
            "hosts": [],
            "findings": [],
            "summary": {}
        }
```

Then register in `registry.py`:
```python
PARSER_REGISTRY['mytool'] = MyToolParser
```

## Utility Methods

All parsers inherit from `BaseToolParser`:

```python
# Normalize severity
severity = parser.normalize_severity('critical')  # -> 'critical'

# Extract host from URL
host = parser.extract_host_from_url('http://example.com/path')  # -> 'example.com'

# Filter None values
clean_data = parser.filter_none({'a': 1, 'b': None, 'c': 3})  # -> {'a': 1, 'c': 3}
```

## Testing

```python
import pytest
from utils.parsers import get_parser

def test_my_parser(tmp_path):
    test_file = tmp_path / "test.xml"
    test_file.write_text("<mytool></mytool>")

    parser = get_parser('mytool', str(test_file))
    assert parser.validate()

    data = parser.parse()
    assert data['tool'] == 'mytool'
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Parser not detected | Check file format, try manual selection |
| Parse returns None | Check logs, verify file structure |
| Missing fields | Use `filter_none()`, check tool version |
| Encoding errors | Files parsed with `utf-8` + error handling |

## API Reference

| Function | Description |
|----------|-------------|
| `detect_parser(path)` | Auto-detect and return parser |
| `get_parser(tool, path)` | Get parser by tool name |
| `list_tools()` | Get list of supported tools |
| `is_tool_supported(tool)` | Check if tool is supported |
| `get_tool_info()` | Get detailed tool information |

## File Locations

```
utils/parsers/
├── base_parser.py          # Base class
├── nmap_parser.py          # Nmap
├── burp_parser.py          # Burp Suite
├── nessus_parser.py        # Nessus
├── zap_parser.py           # OWASP ZAP
├── qualys_parser.py        # Qualys
├── nuclei_parser.py        # Nuclei
├── metasploit_parser.py    # Metasploit
├── acunetix_parser.py      # Acunetix
├── insightvm_parser.py     # InsightVM
├── bloodhound_parser.py    # BloodHound
├── crackmapexec_parser.py  # CrackMapExec
└── registry.py             # Registry and auto-detection
```

## Full Documentation

See `docs/TOOL_PARSERS.md` for complete documentation.

---

**Version:** 1.0
**Last Updated:** February 9, 2026

# XML Parsing Patterns Reference

## Contents
- XXE Prevention (Security)
- Parser Architecture
- lxml Parsing Patterns
- Element Access Patterns
- Severity Mapping
- Anti-Patterns

## XXE Prevention (Security)

### The Actual Pattern in This Codebase

PTVault uses `lxml.etree.XMLParser(resolve_entities=False)` — NOT `defusedxml`. Despite `defusedxml` being in `requirements.txt`, the actual parsers use lxml directly.

```python
# ACTUAL PATTERN — used by Nessus, Burp, ZAP, Qualys, Metasploit, Acunetix, InsightVM
from lxml import etree

parser = etree.XMLParser(resolve_entities=False)
tree = etree.parse(file_path, parser)
root = tree.getroot()
```

This is safe because `resolve_entities=False` disables external entity expansion. Every new XML parser MUST use this pattern.

### WARNING: Stdlib xml.etree.ElementTree is XXE-Vulnerable

**The Problem:**

```python
# BAD — Found in nmap_parser.py:11,31 and routes/evidence.py:21,78
import xml.etree.ElementTree as ET
tree = ET.parse(file_path)  # Attacker can exfiltrate local files
```

**Why This Breaks:**
1. Attacker uploads crafted XML: `<!ENTITY xxe SYSTEM "file:///etc/shadow">`
2. stdlib parser resolves the entity, reading the file
3. File contents appear in parsed element text — attacker exfiltrates via error messages or stored data
4. Can also trigger SSRF via `SYSTEM "http://internal-server/"`

**The Fix:**

```python
# GOOD — lxml with entity resolution disabled
from lxml import etree

parser = etree.XMLParser(resolve_entities=False)
tree = etree.parse(file_path, parser)
root = tree.getroot()
```

**Known Vulnerable Locations:**
- `utils/parsers/nmap_parser.py:31` — `validate()` uses `ET.parse(file_path)`
- `routes/evidence.py:78` — `detect_tool_type()` uses `ET.parse(file_path)`

## Parser Architecture

### Two Parser Styles in the Codebase

**Style 1: Standalone (Nmap, Nessus, Burp)** — Do NOT extend `BaseToolParser`. Accept `file_path` as method argument. These were written first and predate the base class.

```python
# utils/parsers/nessus_parser.py — standalone style
class NessusToolParser:
    def validate(self, file_path):
        parser = etree.XMLParser(resolve_entities=False)
        tree = etree.parse(file_path, parser)
        return tree.getroot().tag == 'NessusClientData_v2'

    def parse(self, file_path):
        parser = etree.XMLParser(resolve_entities=False)
        tree = etree.parse(file_path, parser)
        root = tree.getroot()
        # ... extract data ...
```

**Style 2: BaseToolParser subclass (ZAP, Qualys, Nuclei, etc.)** — Accept `file_path` in `__init__`, use `self.file_path` as default. Gain `normalize_severity()`, `safe_text()`, `filter_none()`, `extract_host_from_url()`.

```python
# utils/parsers/zap_parser.py — BaseToolParser style
from .base_parser import BaseToolParser

class ZAPParser(BaseToolParser):
    def validate(self, file_path=None):
        path = file_path or self.file_path
        parser = etree.XMLParser(resolve_entities=False)
        tree = etree.parse(path, parser)
        return tree.getroot().tag == 'OWASPZAPReport'

    def parse(self, file_path=None):
        path = file_path or self.file_path
        # ... use self.normalize_severity(), self.filter_none() ...
```

**For new parsers:** Always extend `BaseToolParser` (Style 2). The utility methods prevent common bugs.

### Registry and Auto-Detection

`utils/parsers/registry.py` maps tool names (with aliases) to parser classes:

```python
PARSER_REGISTRY = {
    'nmap': NmapToolParser,
    'burp': BurpToolParser,
    'burp_suite': BurpToolParser,   # alias
    'nessus': NessusToolParser,
    'zap': ZAPParser,
    'owasp_zap': ZAPParser,         # alias
    # ... 11 parsers, 15 entries total
}
```

`detect_parser()` tries each parser's `validate()` in priority order (nmap first, then burp, nessus, etc.). Returns the first parser that validates successfully.

## Element Access Patterns

### Safe Attribute Access

```python
# From nessus_parser.py — get attribute with fallback
severity = int(item.get('severity', 0))
plugin_id = item.get('pluginID')
host_name = report_host.get('name')
```

### Safe Text Extraction

```python
# findtext() — returns default if element missing (PREFERRED)
synopsis = item.findtext('synopsis')          # Returns None if missing
solution = item.findtext('solution', '')       # Returns '' if missing

# BaseToolParser.safe_text() — handles None element AND empty text
text = self.safe_text(element, default="")
```

### WARNING: Using find().text on Optional Elements

**The Problem:**

```python
# BAD — crashes when element doesn't exist
version = root.find('version').text  # AttributeError if find() returns None
```

**Why This Breaks:**
`find()` returns `None` for missing elements. `.text` on `None` raises `AttributeError`. Tool outputs vary wildly — elements present in one scan may be absent in another.

**The Fix:**

```python
# GOOD — findtext with default
version = root.findtext('version', 'unknown')

# GOOD — explicit None check
elem = root.find('version')
version = elem.text if elem is not None else 'unknown'
```

## Severity Mapping

Each tool uses different severity schemes. PTVault normalizes to: `critical`, `high`, `medium`, `low`, `info`.

| Tool | Scheme | Mapping |
|------|--------|---------|
| Nessus | 0-4 integers | 0=info, 1=low, 2=medium, 3=high, 4=critical |
| ZAP | 0-3 risk codes | 0=info, 1=low, 2=medium, 3=high |
| Qualys | 0-5 integers | 0=info, 1=low, 2=medium, 3=high, 4-5=critical |
| Burp | Text strings | Information, Low, Medium, High |
| Metasploit | Heuristic | Keyword matching on vuln name (no native severity) |

```python
# Qualys custom mapping (utils/parsers/qualys_parser.py)
def _map_qualys_severity(self, severity):
    severity_map = {'5': 'critical', '4': 'critical', '3': 'high',
                    '2': 'medium', '1': 'low', '0': 'info'}
    return severity_map.get(severity, self.normalize_severity(severity))
```

## Anti-Patterns

### WARNING: Not Validating Root Element

**The Problem:**

```python
# BAD — silently parses wrong file type, returns empty results
def parse_nmap(file_path):
    tree = etree.parse(file_path, etree.XMLParser(resolve_entities=False))
    root = tree.getroot()
    for host in root.findall('.//host'):  # Returns [] for non-Nmap files
        ...
```

**Why This Breaks:**
User uploads a Burp XML thinking it's Nmap. Parser silently returns zero hosts. No error, no warning — data just disappears. Debugging is painful.

**The Fix:**

```python
# GOOD — validate root element tag
def validate(self, file_path):
    parser = etree.XMLParser(resolve_entities=False)
    tree = etree.parse(file_path, parser)
    return tree.getroot().tag == 'nmaprun'
```

### WARNING: Parsing XML Twice (validate + parse)

Most parsers parse the file once in `validate()` and again in `parse()`. This is intentional — `validate()` is called during auto-detection across all parsers, and only one parser's `parse()` runs. Do NOT try to cache the parsed tree across methods — it complicates the registry pattern for negligible gain.

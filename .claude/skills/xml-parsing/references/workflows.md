# XML Parsing Workflows Reference

## Contents
- Adding a New Tool Parser
- Testing Parsers
- Importing Tool Output via API
- Debugging Parse Failures

## Adding a New Tool Parser

### Workflow Checklist

Copy this checklist and track progress:
- [ ] Create parser in `utils/parsers/<tool>_parser.py` extending `BaseToolParser`
- [ ] Use `lxml.etree.XMLParser(resolve_entities=False)` for all XML parsing
- [ ] Implement `validate()` checking root element tag
- [ ] Implement `parse()` returning standardized dict
- [ ] Register in `utils/parsers/registry.py` PARSER_REGISTRY
- [ ] Import in `registry.py` at top of file
- [ ] Add to `detection_order` list in `detect_parser()`
- [ ] Add to `get_tool_info()` metadata dict
- [ ] Add test fixtures in `tests/fixtures/`
- [ ] Write unit tests in `tests/parsers/`
- [ ] Run tests: `python -m pytest tests/parsers/ -v`

### Step 1: Create Parser Class

```python
# utils/parsers/nikto_parser.py
import logging
from lxml import etree
from typing import Dict, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class NiktoParser(BaseToolParser):
    """Parser for Nikto XML scan output."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            return tree.getroot().tag == 'niktoscan'
        except Exception as e:
            logger.debug(f"Nikto validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            metadata = {
                "tool": "nikto",
                "summary": {"total_findings": 0},
                "hosts": [],
                "findings": []
            }

            for item in root.findall('.//item'):
                severity = self.normalize_severity(item.get('osvdbid', 'info'))
                finding = {
                    'title': item.findtext('description', ''),
                    'severity': severity,
                    'url': item.findtext('uri', ''),
                    'method': item.findtext('method', 'GET'),
                    'tool': 'Nikto'
                }
                finding = self.filter_none(finding)
                metadata['findings'].append(finding)

            metadata['summary']['total_findings'] = len(metadata['findings'])
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"Nikto XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing Nikto file {path}: {e}")
            return None
```

### Step 2: Register in Registry

Location: `utils/parsers/registry.py`

```python
# Add import at top
from .nikto_parser import NiktoParser

# Add to PARSER_REGISTRY dict
PARSER_REGISTRY: Dict[str, Type[BaseToolParser]] = {
    # ... existing entries ...
    'nikto': NiktoParser,
}

# Add to detection_order in detect_parser()
detection_order = [
    'nmap', 'burp_suite', 'nessus', 'zap', 'nuclei',
    'qualys', 'metasploit', 'acunetix', 'insightvm',
    'bloodhound', 'crackmapexec',
    'nikto',  # Add at end (lower priority for detection)
]

# Add to get_tool_info()
'nikto': {
    'name': 'Nikto',
    'description': 'Web server scanner',
    'formats': ['XML'],
    'aliases': []
},
```

### Step 3: Validate

1. Run parser tests: `python -m pytest tests/parsers/ -v`
2. If tests fail, fix parser and repeat
3. Test with real tool output if available
4. Only proceed when all tests pass

## Testing Parsers

### Test File Structure

```
tests/
├── fixtures/
│   ├── nikto_sample.xml        # Real or realistic tool output
│   ├── nikto_empty.xml         # Valid XML, no findings
│   └── nikto_malformed.xml     # Invalid XML for error handling
└── parsers/
    └── test_nikto_parser.py
```

### Writing Parser Tests

```python
# tests/parsers/test_nikto_parser.py
import os
import pytest
from utils.parsers.nikto_parser import NiktoParser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '..', 'fixtures')


@pytest.fixture
def parser(tmp_path):
    """Create parser with a temp file path."""
    return NiktoParser(str(tmp_path / 'test.xml'))


def test_validate_correct_format(parser, tmp_path):
    xml_file = tmp_path / 'nikto.xml'
    xml_file.write_text('<niktoscan><item></item></niktoscan>')
    assert parser.validate(str(xml_file)) is True


def test_validate_wrong_format(parser, tmp_path):
    xml_file = tmp_path / 'nmap.xml'
    xml_file.write_text('<nmaprun></nmaprun>')
    assert parser.validate(str(xml_file)) is False


def test_validate_invalid_xml(parser, tmp_path):
    xml_file = tmp_path / 'bad.xml'
    xml_file.write_text('not xml at all')
    assert parser.validate(str(xml_file)) is False


def test_parse_extracts_findings(parser, tmp_path):
    xml_file = tmp_path / 'nikto.xml'
    xml_file.write_text('''<niktoscan>
        <item><description>Directory indexing found</description>
        <uri>/admin/</uri><method>GET</method></item>
    </niktoscan>''')
    result = parser.parse(str(xml_file))
    assert result is not None
    assert result['tool'] == 'nikto'
    assert len(result['findings']) == 1
    assert result['findings'][0]['title'] == 'Directory indexing found'


def test_parse_returns_none_on_bad_xml(parser, tmp_path):
    xml_file = tmp_path / 'bad.xml'
    xml_file.write_text('<<<not valid xml>>>')
    result = parser.parse(str(xml_file))
    assert result is None
```

### Running Tests

```bash
# Single parser
python -m pytest tests/parsers/test_nikto_parser.py -v

# All parser tests
python -m pytest tests/parsers/ -v

# All tests including existing parsers
python -m pytest tests/ -k parser -v
```

**Validation Loop:**
1. Write/modify parser code
2. Run: `python -m pytest tests/parsers/test_nikto_parser.py -v`
3. If tests fail, fix parser and repeat step 2
4. Only proceed when all tests pass

## Importing Tool Output via API

### How Import Works (routes/evidence.py)

1. User uploads file via `POST /api/evidence` with `type=tool_output`
2. `detect_tool_type()` checks root XML element (WARNING: uses vulnerable stdlib ET)
3. `parse_tool_output()` instantiates the correct parser and calls `parse()`
4. Parsed metadata stored as JSON in the `metadata` column of `evidence` table
5. `auto_generate_tags()` creates tags from parsed metadata
6. `extract_and_link_hosts_for_evidence()` auto-creates host entries

### The Import Path (evidence.py:93-126)

```python
# routes/evidence.py — existing flow (simplified)
def parse_tool_output(file_path, tool_type):
    parsers = {
        'nmap': nmap_parser.NmapToolParser(),
        'burp': burp_parser.BurpToolParser(),
        'nessus': nessus_parser.NessusToolParser()
    }
    parser = parsers.get(tool_type)
    return parser.parse(file_path)
```

Note: Only 3 parsers are wired into `routes/evidence.py`. The full 11-parser registry in `utils/parsers/registry.py` is available but not yet integrated into the evidence route. To use the registry:

```python
from utils.parsers.registry import get_parser, detect_parser

# Replace detect_tool_type() with:
parser = detect_parser(file_path)
if parser:
    result = parser.parse(file_path)
```

### Frontend Integration

See the **javascript** skill for API client patterns.

```javascript
// static/js/hosts.js — existing import UI
async function importToolOutput(toolType, file) {
    const formData = new FormData();
    formData.append('type', 'tool_output');
    formData.append('title', file.name);
    formData.append('content', 'Tool output import');
    formData.append('file', file);
    const response = await fetch('/api/evidence', {
        method: 'POST', body: formData
    });
}
```

## Debugging Parse Failures

### Common Issues

| Error | Cause | Fix |
|-------|-------|-----|
| `XMLSyntaxError: not well-formed` | Corrupted or truncated XML | Validate with `xmllint --noout file.xml` |
| `ValueError: Unknown tool` | Tool name not in registry | Check `list_tools()` for supported names |
| `AttributeError: NoneType` | Missing XML element | Use `findtext()` with default value |
| `NmapParserException` | Invalid Nmap XML structure | Verify file was exported with `nmap -oX` |
| `UnicodeDecodeError` | Binary file or wrong encoding | Check file type with `file scan.xml` |
| Returns `None`, no error | Parser catches exception internally | Check application logs for parser errors |

### Debug Approach

```python
# Quick debug in Python REPL
from lxml import etree

parser = etree.XMLParser(resolve_entities=False)
tree = etree.parse('problem_file.xml', parser)
root = tree.getroot()
print(f"Root: {root.tag}")
print(f"Attrs: {root.attrib}")
print(f"Children: {[c.tag for c in root][:10]}")
```

### Using the Registry for Detection

```python
from utils.parsers.registry import detect_parser, list_tools

# What tools are supported?
print(list_tools())

# What parser matches this file?
parser = detect_parser('/path/to/mystery.xml')
if parser:
    print(f"Detected: {parser.tool_name}")
else:
    print("No parser matched — check root element tag")
```

### xmllint Validation

```bash
# Check if XML is well-formed
xmllint --noout scan_results.xml

# Pretty-print to inspect structure
xmllint --format scan_results.xml | head -50

# Count elements
xmllint --xpath 'count(//ReportHost)' scan.nessus
```

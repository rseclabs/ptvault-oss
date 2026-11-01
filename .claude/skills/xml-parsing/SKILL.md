All three skill files have been written. Here's a summary of what was updated:

**SKILL.md** (101 lines) — Rewrote to accurately reflect the codebase:
- Corrected the XXE warning: parsers use `lxml.etree.XMLParser(resolve_entities=False)`, NOT `defusedxml` as previously claimed
- Flagged the specific vulnerable locations (nmap_parser.py validate + evidence.py detect_tool_type using stdlib ET)
- Added complete 11-tool support table with BaseToolParser inheritance status
- Added parser registry usage patterns

**references/patterns.md** (214 lines) — Comprehensive rewrite:
- Documents the actual XXE prevention pattern (`lxml` with `resolve_entities=False`)
- Explains the two parser styles (standalone vs BaseToolParser subclass) with real code
- Severity mapping table across all 5 tool-specific schemes
- Safe element access patterns (findtext vs find().text)
- Anti-patterns: missing root validation, double-parsing explanation

**references/workflows.md** (323 lines) — Detailed rewrite:
- 11-step checklist for adding a new parser
- Complete parser template extending BaseToolParser with proper lxml usage
- Registry registration steps (PARSER_REGISTRY, detection_order, get_tool_info)
- Test structure and pytest examples with `tmp_path` fixture
- Documents the evidence.py import flow and the gap between 3-parser route vs 11-parser registry
- Debugging table with common errors and fixes
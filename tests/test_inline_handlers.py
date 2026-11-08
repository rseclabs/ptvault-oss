"""H-10: inline event handlers never carry stored text.

The browser decodes HTML entities in an onclick="..." attribute before it runs
the code, so escapeHtml() cannot protect a string placed inside one. Data goes
in data-* attributes and is read by a registerAction() handler instead.

This test parses every inline handler in static/js and templates and fails on
any ${...} interpolation that is not a loop index or a value reviewed below.
A new handler that needs data should use data-* + registerAction(); add an
entry here only for an integer primary key or a constant.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
HANDLER_START = re.compile(r'\bon[a-z]+\s*=\s*"')
LOOP_INDEX = re.compile(r'^(i|j|ri|ci|idx|index|rowIdx|colIdx)$')

# Integer primary keys from the API (SQLite INTEGER PRIMARY KEY), constants
# defined in the same file, or values the code computes itself.
INTEGER_IDS = {
    'eng.id', 'item.id', 'edge.id', 'node.id', 'client.id', 'cmd.id', 'cred.id', 'dump.id', 'ev.id',
    'finding.id', 'host.id', 'note.id', 'port.id', 'vuln.id', 'rel.id', 'template.id', 'writeup.id',
    'member.id', 'team.id', 'atomic.id', 'atomicId', 'e.id', 'exec.id', 'layer.id', 'plan.id', 'planId',
    'test.id', 'user.id', 'member.member_id', "isEdit ? plan.id : 'null'",
}
REVIEWED = {
    # admin.js: item.id is a tab id from the constant nav list (and oneliner integer ids).
    # reporting.js: report item ids are normalised to [A-Za-z0-9_-] by hydrate_report_item and on load;
    # toolId is only used when it is in the constant editableTools list; tool.id and col are constants.
    ('static/js/reporting.js', 'toolId'), ('static/js/reporting.js', 'tool.id'), ('static/js/reporting.js', 'col'),
    # tools.js: keys of constant tables, CVSS metric constants, subnet calculator output.
    ('static/js/tools.js', 'key'), ('static/js/tools.js', 'metricKey'), ('static/js/tools.js', 'opt.value'),
    ('static/js/tools.js', 'r.networkAddress'), ('static/js/tools.js', 'r.broadcastAddress'),
    ('static/js/tools.js', 'r.firstUsable'), ('static/js/tools.js', 'r.lastUsable'),
    ('static/js/tools.js', 'r.subnetMask'), ('static/js/tools.js', 'r.wildcardMask'),
}


def _interpolations(source, pos):
    """Yield (expression, offset) for each ${...} in the attribute value starting at pos."""
    i = pos
    while i < len(source):
        if source[i] == '"':
            return
        if source.startswith('${', i):
            depth, j = 1, i + 2
            while j < len(source) and depth:
                ch = source[j]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                elif ch in '\'"`':
                    j += 1
                    while j < len(source) and source[j] != ch:
                        j += 2 if source[j] == '\\' else 1
                j += 1
            yield source[i + 2:j - 1].strip(), i
            i = j
            continue
        i += 1


def _handler_interpolations():
    files = sorted(list((ROOT / 'static/js').rglob('*.js')) + list((ROOT / 'templates').rglob('*.html')))
    for path in files:
        source = path.read_text()
        rel = str(path.relative_to(ROOT))
        for match in HANDLER_START.finditer(source):
            for expr, offset in _interpolations(source, match.end()):
                yield rel, source.count('\n', 0, offset) + 1, expr


def test_inline_handlers_interpolate_only_ids_and_constants():
    unexpected = [
        f'{rel}:{line}: ${{{expr}}}'
        for rel, line, expr in _handler_interpolations()
        if not LOOP_INDEX.match(expr) and expr not in INTEGER_IDS and (rel, expr) not in REVIEWED
    ]
    assert not unexpected, 'stored text inside inline handlers (use data-* + registerAction):\n' + '\n'.join(unexpected)


def test_scanner_finds_a_string_argument():
    # Guard against the scanner silently matching nothing.
    sample = """x = `<b onclick="M.f('${escapeHtml(name).replace(/'/g, "\\\\'")}')">`"""
    found = [expr for m in HANDLER_START.finditer(sample) for expr, _ in _interpolations(sample, m.end())]
    assert found and found[0].startswith('escapeHtml(name)')

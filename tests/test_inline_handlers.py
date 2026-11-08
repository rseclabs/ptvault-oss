"""No inline script anywhere in the UI (L-21, after H-10).

The Content-Security-Policy allows scripts only from files ('self'), so an
inline handler or <script> block would simply not run. Handlers are declared
instead: data-on-click='["Obj.method", args...]', built in JS with on() from
static/js/utils.js. This test fails on any on*="..." attribute, inline
<script> block or javascript: URL in the templates and the JS that renders
markup, so one cannot be added by accident.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = sorted(list((ROOT / 'static/js').rglob('*.js')) + list((ROOT / 'templates').rglob('*.html')))
INLINE_HANDLER = re.compile(r'(?<![\w-])on[a-z]+\s*=\s*["\']')
INLINE_SCRIPT = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>', re.I)
JS_URL = re.compile(r'''(href|src|action)\s*=\s*["']\s*javascript:''', re.I)
# Comments describing the old style are fine; strip them before scanning.
JS_COMMENT = re.compile(r'/\*.*?\*/|(?<![:"\'\\])//[^\n]*', re.S)
HTML_COMMENT = re.compile(r'<!--.*?-->', re.S)


def _code(path):
    text = path.read_text()
    return HTML_COMMENT.sub('', text) if path.suffix == '.html' else JS_COMMENT.sub('', text)


def _matches(pattern):
    found = []
    for path in SOURCES:
        text = _code(path)
        for m in pattern.finditer(text):
            found.append(f'{path.relative_to(ROOT)}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0)}')
    return found


def test_no_inline_event_handlers():
    assert _matches(INLINE_HANDLER) == [], 'use data-on-* / on() (static/js/utils.js) instead'


def test_no_inline_script_blocks_in_templates():
    found = [f for f in _matches(INLINE_SCRIPT) if f.startswith('templates/')]
    assert found == [], 'move the script to a file under static/js'


def test_no_javascript_urls():
    assert _matches(JS_URL) == []


def test_the_scanner_still_finds_what_it_looks_for():
    # Guard against the patterns silently matching nothing.
    assert INLINE_HANDLER.search('<b onclick="x()">') and INLINE_HANDLER.search("<b onerror='x'>")
    assert not INLINE_HANDLER.search('<b data-on-click=\'["x"]\'>')
    assert INLINE_SCRIPT.search('<script>x</script>') and not INLINE_SCRIPT.search('<script src="/a.js">')
    assert JS_URL.search('<a href="javascript:alert(1)">')

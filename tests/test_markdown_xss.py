"""H-9: Markdown is sanitized before it becomes HTML.

marked passes raw HTML through, and imported scan output (Burp issueDetail,
Nessus description and plugin_output) lands in finding Markdown. Every render
goes through one renderer, renderMarkdown(), which sanitizes marked's output
with the vendored DOMPurify; every EasyMDE preview uses it; scan text is
escaped and fenced before it is put into Markdown.
"""

import pathlib
import re

import pytest

from tests.test_browser_xss import AUDIT, browser, ui  # noqa: F401  (fixtures)

ROOT = pathlib.Path(__file__).resolve().parent.parent
RENDERER = 'static/js/lib/markdown.js'

# Raw HTML and link payloads a hostile scanned service (or teammate) can put in Markdown.
MD = '\n\n'.join([
    '<img src=x data-pwn=1 onerror="window.__xss.push(\'img\')">',
    '[click](javascript:window.__xss.push(\'link\'))',
    '<a href="jAvAsCrIpT:window.__xss.push(\'a\')">a</a>',
    '<svg><script>window.__xss.push(\'svg\')</script></svg>',
    '<iframe srcdoc="<script>parent.__xss.push(\'iframe\')</script>"></iframe>',
    '<details open ontoggle="window.__xss.push(\'toggle\')">x</details>',
    '<div data-action="confirm-delete-engagement" data-engagement-id="1">clobber</div>',
    '<input id="editItemCommand" name="x"><form action="/x"><button formaction="/y">b</button></form>',
    '<p style="background:url(/api/x)">styled</p>',
])

SANITIZED_DOM = """root => ({
    script: root.querySelectorAll('script, iframe, object, embed, form, button, style').length,
    dataAttrs: [...root.querySelectorAll('*')].filter(el => [...el.attributes].some(a => a.name.startsWith('data-'))).length,
    ids: root.querySelectorAll('[id], [name], [style]').length,
    jsLinks: [...root.querySelectorAll('a[href]')].filter(a => !/^(https?:|mailto:|#|\\/)/i.test(a.getAttribute('href'))).length,
})"""


def _clean(page):
    page.wait_for_timeout(150)
    assert page.evaluate(AUDIT) == {'injected': 0, 'handlers': [], 'fired': []}


# ------------------------------------------------------------------ source checks

def _sources():
    for path in sorted(list((ROOT / 'static/js').rglob('*.js')) + list((ROOT / 'templates').rglob('*.html'))):
        yield str(path.relative_to(ROOT)), path.read_text()


def test_marked_is_only_called_by_the_sanitizing_renderer():
    calls = [f'{rel}:{src.count(chr(10), 0, m.start()) + 1}'
             for rel, src in _sources() if rel != RENDERER
             for m in re.finditer(r'\bmarked\s*(\.\s*parse(Inline)?\s*)?\(', src)]
    assert not calls, 'call renderMarkdown() instead of marked: ' + ', '.join(calls)


def test_every_easymde_preview_uses_the_renderer():
    for rel, src in _sources():
        if 'new EasyMDE(' not in src:
            continue
        renders = re.findall(r'previewRender\s*(?::|\()([^\n]*\n?[^\n]*)', src)
        assert renders, f'{rel}: EasyMDE without previewRender (its bundled marked does not sanitize)'
        for body in renders:
            assert 'renderMarkdown' in body, f'{rel}: previewRender does not use renderMarkdown: {body!r}'


def test_pages_with_markdown_load_dompurify_before_the_renderer():
    for rel in ('templates/dashboard.html', 'templates/note_editor.html', 'templates/finding_editor.html'):
        src = (ROOT / rel).read_text()
        purify, renderer = src.find('/static/vendor/dompurify-'), src.find('/static/js/lib/markdown.js')
        assert 0 <= purify < renderer, rel


# ------------------------------------------------------------------ renderer

def test_renderer_strips_script_and_gadgets(ui):
    counts = ui.page.evaluate(f"""md => {{
        const box = document.getElementById('xssScratch');
        box.innerHTML = renderMarkdown(md);
        return ({SANITIZED_DOM})(box);
    }}""", MD)
    assert counts == {'script': 0, 'dataAttrs': 0, 'ids': 0, 'jsLinks': 0}
    _clean(ui.page)


def test_renderer_keeps_ordinary_markdown(ui):
    html = ui.page.evaluate("""() => renderMarkdown(
        '**bold** [site](https://example.com) ![s](/api/evidence/1/file)\\n\\n```\\ncode <b>\\n```\\n\\n- [x] done')""")
    for expected in ('<strong>bold</strong>', 'href="https://example.com"', 'src="/api/evidence/1/file"',
                     '<code>code &lt;b&gt;', 'type="checkbox"'):
        assert expected in html, (expected, html)


def test_renderer_fails_closed_without_dompurify(ui):
    html = ui.page.evaluate("""() => {
        const saved = window.DOMPurify;
        window.DOMPurify = undefined;
        try { return renderMarkdown('<img src=x onerror=alert(1)> **b**'); } finally { window.DOMPurify = saved; }
    }""")
    assert '<img' not in html and '&lt;img' in html


# ------------------------------------------------------------------ views

def test_report_preview_and_writeup_bodies(ui):
    ui.page.evaluate("""md => {
        ReportingManager.workspaceItems = [
            { id: 'a', writeup_type: 'finding', title: 't', criticality: 'high', finding_content: md, remediation_content: md },
            { id: 'b', writeup_type: 'narrative', title: 't', finding_content: md },
            { id: 'c', writeup_type: 'format_tool', format_tool_id: 'textblock', toolData: { content: md } },
            { id: 'd', writeup_type: 'format_tool', format_tool_id: 'twocolumn', toolData: { leftContent: md, rightContent: md } },
        ];
        document.getElementById('reportPreview').innerHTML = ReportingManager.renderPreview();
    }""", MD)
    _clean(ui.page)


def test_engagement_findings_and_live_previews(ui):
    ui.page.evaluate("""md => {
        const box = document.getElementById('xssScratch');
        box.innerHTML = '<textarea id="mdIn"></textarea><div id="mdOut"></div>';
        document.getElementById('mdIn').value = md;
        HostManager.updateNotePreview('mdIn', 'mdOut');
        HostManager.updateFindingPreview('mdIn', 'mdOut');
        ReportingManager.updatePreview('mdIn', 'mdOut');
        HostManager.engagementFindings = [{ id: 1, title: 't', criticality: 'high', cvss_score: 5, finding_content: md,
                                            remediation_content: md }];
        HostManager.renderEngagementFindings();
    }""", MD)
    _clean(ui.page)


# ------------------------------------------------------------------ imported scan output

def test_scan_output_cannot_close_the_fence_or_inject_markup(ui):
    hostile = '```\n<img src=x data-pwn=1 onerror="window.__xss.push(\'fence\')">\n````\n<b>x</b>'
    result = ui.page.evaluate("""h => {
        const md = HostManager._buildFindingMarkdown({
            synopsis: h, description: h, plugin_output: h, location: h, source_tool: h, port: h, protocol: h,
            cves: ['CVE-2024-1234', '](javascript:window.__xss.push(1))'],
        });
        const box = document.getElementById('xssScratch');
        box.innerHTML = renderMarkdown(md);
        const pre = box.querySelector('pre code');
        return { pre: pre ? pre.textContent : null, links: [...box.querySelectorAll('a')].map(a => a.getAttribute('href')),
                 bold: box.querySelectorAll('b').length };
    }""", hostile)
    assert result['pre'] is not None and hostile in result['pre']   # the whole output stays inside one code block
    assert result['links'] == ['https://nvd.nist.gov/vuln/detail/CVE-2024-1234']
    assert result['bold'] == 0                                    # scanner HTML is shown as text
    _clean(ui.page)


# ------------------------------------------------------------------ standalone editors

@pytest.mark.parametrize('route, editors', [
    ('/note/new', ['easyMDE']),
    ('/finding/new', ['findingMDE', 'remediationMDE']),
])
def test_editor_pages_preview_through_the_renderer(ui, route, editors):
    ui.page.goto(ui.base + route)
    ui.page.wait_for_function('() => typeof EasyMDE === "function"')
    for name in editors:
        html = ui.page.evaluate(f'md => {name}.options.previewRender(md)', MD)
        assert 'onerror' not in html and 'javascript:' not in html.lower() and '<script' not in html, (name, html)

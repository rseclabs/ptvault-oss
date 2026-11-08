"""L-1: the site-wide Content-Security-Policy is as tight as the app allows.

Only CyberChef evaluates code at runtime, so 'unsafe-eval' is limited to its
path; no directive names an external host (CyberChef is bundled locally);
plugins, <base> and framing by other sites are blocked. Scripts may not be
inline (L-21): handlers are declared in data-on-* attributes, so an unescaped
<img onerror> or injected <script> is refused by the browser.

The browser test loads the real pages under the real headers and fails on
any CSP violation, so a library that needs eval would be caught here.
"""

import pytest
from flask import Flask

from tests.test_browser_xss import browser, ui  # noqa: F401  (fixtures)
from utils.security_headers import CYBERCHEF_CSP, DEFAULT_CSP, apply_security_headers


def _directives(csp):
    return {name: value for name, _, value in (p.strip().partition(' ') for p in csp.split(';') if p.strip())}


def test_default_policy_allows_no_inline_script():
    assert _directives(DEFAULT_CSP)['script-src'] == "'self'"


def test_default_policy_has_no_eval_and_no_external_host():
    d = _directives(DEFAULT_CSP)
    assert "'unsafe-eval'" not in DEFAULT_CSP
    assert 'http' not in DEFAULT_CSP, 'CSP names an external host'
    assert d['frame-src'] == "'self'"


@pytest.mark.parametrize('directive, value', [
    ('object-src', "'none'"), ('base-uri', "'self'"), ('form-action', "'self'"), ('frame-ancestors', "'none'"),
])
def test_default_policy_hardening_directives(directive, value):
    assert _directives(DEFAULT_CSP).get(directive) == value


def test_eval_is_allowed_only_on_the_cyberchef_path():
    app = Flask(__name__)
    app.after_request(apply_security_headers)
    app.add_url_rule('/api/admin/cyberchef', 'cc', lambda: 'cc')
    app.add_url_rule('/dashboard', 'dash', lambda: 'dash')
    client = app.test_client()
    assert client.get('/api/admin/cyberchef').headers['Content-Security-Policy'] == CYBERCHEF_CSP
    assert "'unsafe-eval'" not in client.get('/dashboard').headers['Content-Security-Policy']


# ------------------------------------------------------------------ real pages under the real policy

VIOLATIONS = """() => window.__cspViolations.map(v => `${v.violatedDirective} ${v.blockedURI} ${v.sourceFile}:${v.lineNumber}`)"""


@pytest.mark.parametrize('route', ['/dashboard', '/note/new', '/finding/new', '/login', '/setup', '/unlock-preview'])
def test_pages_run_under_the_policy_without_violations(ui, route):
    page = ui.page
    page.add_init_script("""
        window.__cspViolations = [];
        document.addEventListener('securitypolicyviolation', e => window.__cspViolations.push(e));
    """)
    page.goto(ui.base + route)
    page.wait_for_load_state('networkidle')
    csp = page.evaluate("async () => (await fetch(location.href)).headers.get('content-security-policy')")
    assert csp == DEFAULT_CSP
    if route == '/dashboard':
        # Exercise the libraries: Markdown, icons, and a D3 graph render.
        page.evaluate("""() => {
            document.body.insertAdjacentHTML('beforeend', '<div id="cspProbe"></div>');
            document.getElementById('cspProbe').innerHTML = renderMarkdown('**x** `y`') + '<i data-lucide="map"></i>';
            lucide.createIcons();
            d3.select('#cspProbe').append('svg').append('circle').attr('r', 3);
        }""")
    assert page.evaluate(VIOLATIONS) == []
    # The policy is in force: an injected inline script and an inline handler do not run
    # (L-21), and the browser reports both. Code Playwright evaluates is exempt from CSP;
    # what it inserts into the page is not.
    page.evaluate("""() => {
        const s = document.createElement('script');
        s.textContent = "window.__inlineProbe = 'ran'";
        document.head.appendChild(s);
        document.body.insertAdjacentHTML('beforeend', '<img id="cspImg" src="data:," onerror="window.__inlineProbe = 1">');
    }""")
    page.wait_for_function('() => window.__cspViolations.length >= 2')
    assert page.evaluate('() => window.__inlineProbe') is None
    assert all(v.startswith('script-src') for v in page.evaluate(VIOLATIONS))

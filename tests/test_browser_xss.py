"""H-10 in a real browser: stored text renders as text, never as markup or code.

The real dashboard (templates + static JS) is served over the live_app
blueprints, and each view the report names is rendered with hostile values.
After rendering, nothing may have executed, no element may have been
injected, and no inline handler may contain the hostile text. The handlers
converted to data-* attributes must still receive the exact original value.

Runs headless Chromium through Playwright; skipped if it is not installed.
"""

import io
import json
import os
import threading

import pytest
from flask import render_template
from werkzeug.serving import make_server

from tests.conftest import ENGAGEMENT_A

sync_api = pytest.importorskip('playwright.sync_api')

# Breaks out of attributes, element content, single-quoted JS strings and template literals.
P = ('x"\'><b data-pwn=1>B</b><img src=x data-pwn=1 onerror="window.__xss.push(\'img\')">'
     '\');window.__xss.push(\'js\');//`${window.__xss.push(\'tpl\')}`\\n')

AUDIT = """() => {
    const handlers = [];
    for (const el of document.querySelectorAll('*')) {
        for (const a of el.attributes) {
            if (a.name.startsWith('on') && a.value.includes('__xss')) handlers.push(el.outerHTML.slice(0, 160));
        }
    }
    return { injected: document.querySelectorAll('[data-pwn]').length, handlers, fired: window.__xss.slice() };
}"""


@pytest.fixture(scope='module')
def browser():
    with sync_api.sync_playwright() as pw:
        try:
            # PTVAULT_TEST_CHROMIUM points at another Chromium build if Playwright's own is not installed.
            b = pw.chromium.launch(executable_path=os.environ.get('PTVAULT_TEST_CHROMIUM') or None)
        except Exception as e:  # browser binaries not installed
            pytest.skip(f'chromium not available: {e}')
        yield b
        b.close()


@pytest.fixture
def ui(live_app, browser):
    app = live_app.app
    # The pages app.py serves (it cannot be imported in tests); routes must exist before the first request.
    for route, template in (('/dashboard', 'dashboard.html'), ('/note/new', 'note_editor.html'),
                            ('/finding/new', 'finding_editor.html')):
        app.add_url_rule(route, template, lambda t=template: render_template(t))
    # The real security headers (CSP included) that app.py adds to every response.
    from utils.security_headers import apply_security_headers
    app.after_request(apply_security_headers)
    server = make_server('127.0.0.1', 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'

    context = browser.new_context()
    context.add_cookies([{'name': 'auth_token', 'value': live_app.token_for('admin'), 'url': base}])
    assert context.request.post(f'{base}/api/engagements/active',
                                data=json.dumps({'engagement_id': ENGAGEMENT_A}),
                                headers={'Content-Type': 'application/json'}).ok
    page = context.new_page()
    page.goto(f'{base}/dashboard')
    page.wait_for_function("""() => window.API && window.HostManager
        && window.ReportingManager && window.AdminPanel && window.TestPlansManager && window.ShellOneLinersManager
        && window.CommandManager && window.AttackMapEditor && window.ClientManager""")
    page.evaluate("""() => {
        window.__xss = [];
        // Containers for views that are created on navigation.
        for (const id of ['portGridContainer', 'attackMapProperties', 'adminEngagementsList',
                          'shellSubcategoryFilter', 'workspaceItems', 'reportPreview', 'clientsList', 'xssScratch']) {
            if (!document.getElementById(id)) {
                const div = document.createElement('div');
                div.id = id;
                document.body.appendChild(div);
            }
        }
    }""")
    live_app.page, live_app.base = page, base
    yield live_app
    context.close()
    server.shutdown()


def _assert_clean(page):
    page.wait_for_timeout(150)  # let any injected <img onerror> fire
    result = page.evaluate(AUDIT)
    assert result == {'injected': 0, 'handlers': [], 'fired': []}, result


# ------------------------------------------------------------------ helpers

def test_escape_html_encodes_quotes(ui):
    assert ui.page.evaluate("() => escapeHtml(`&<>\"'\\``)") == '&amp;&lt;&gt;&quot;&#39;&#96;'
    assert ui.page.evaluate('() => [escapeHtml(0), escapeHtml(null), escapeHtml(undefined), escapeHtml("")]') == \
        ['0', '', '', '']


@pytest.mark.parametrize('url, expected', [
    ('https://example.com/a', 'https://example.com/a'),
    ('mailto:a@b.c', 'mailto:a@b.c'),
    ('/relative', '/relative'),
    ('javascript:alert(1)', '#'),
    (' JaVaScRiPt:alert(1)', '#'),
    ('java\tscript:alert(1)', '#'),
    ('data:text/html,x', '#'),
])
def test_safe_url(ui, url, expected):
    assert ui.page.evaluate('u => safeUrl(u)', url) == expected


# ------------------------------------------------------------------ hosts

def test_host_list_ports_grid_and_saved_filters(ui):
    ui.page.evaluate("""p => {
        HostManager.hosts = [{ id: 1, ip: '10.0.0.1', color_category: p }];
        HostManager.renderHostList();
        HostManager.currentPorts = [{ id: 1, port: p, protocol: p, state: p, source: p, service: p, version: p }];
        HostManager.renderPorts();
        const grid = { hosts: [{ id: 1, ip: '10.0.0.1' }], ports: [{ port: p, protocol: p, service: p, hosts: { 1: 'open' } }] };
        HostManager.renderPortGrid(grid);
        HostManager.portGridFilter = { port: p, protocol: p };
        HostManager.renderPortGridPage(grid);
        HostManager.savedFilters = [{ id: 1, name: p }];
        HostManager.renderSavedFiltersDropdown();
    }""", P)
    _assert_clean(ui.page)


def test_port_grid_filter_receives_the_port(ui):
    got = ui.page.evaluate("""() => {
        HostManager.portGridFilter = null;
        HostManager.renderPortGridPage({ hosts: [{ id: 1, ip: '10.0.0.1' }],
                                         ports: [{ port: 443, protocol: 'tcp', hosts: { 1: 'open' } }] });
        let got = null;
        const original = HostManager.togglePortFilter;
        HostManager.togglePortFilter = (port, protocol) => { got = [port, protocol]; };
        document.querySelector('#portGridPageContainer [data-action="toggle-port-filter"]').click();
        HostManager.togglePortFilter = original;
        return got;
    }""")
    assert got == [443, 'tcp']


# ------------------------------------------------------------------ reporting

def test_writeup_card(ui):
    ui.page.evaluate("""p => {
        document.getElementById('xssScratch').innerHTML = ReportingManager.renderWriteupCard(
            { id: 1, name: p, description: p, criticality: p, writeup_type: 'finding', category: p });
    }""", P)
    _assert_clean(ui.page)


def test_saved_report_workspace_and_preview(ui):
    tool = lambda tool_id, data, **kw: {'id': P, 'type': 'format_tool', 'format_tool_id': tool_id,
                                        'title': P, 'toolData': data, **kw}
    conn = ui.db()
    writeup_id = conn.execute(
        "INSERT INTO writeups (name, description, remediation, criticality, writeup_type) "
        "VALUES (?, ?, ?, 'high', 'finding')", (P, P, P)).lastrowid
    narrative_id = conn.execute(
        "INSERT INTO writeups (name, description, writeup_type) VALUES (?, ?, 'narrative')", (P, P)).lastrowid
    structure = [
        tool('sectionheader', {'level': P, 'text': P, 'numbered': True, 'number': P}),
        tool(P, {}),
        tool('alertbox', {'type': P, 'content': P}),
        tool('cvsscard', {'score': P, 'vector': P}),
        tool('riskmatrix', {'size': P}),
        tool('imageplaceholder', {'width': P, 'caption': P}),
        tool('attackmap', {'mapId': P, 'mapName': P}),
        {'id': P, 'type': 'writeup', 'source_id': writeup_id,
         'customizations': {'criticality': P, 'heading_level': P, 'cvss_score': P}},
        {'id': P, 'type': 'writeup', 'source_id': narrative_id, 'customizations': {'heading_level': P}},
    ]
    report_id = conn.execute("INSERT INTO reports (engagement_id, name, structure) VALUES (?, ?, ?)",
                             (ENGAGEMENT_A, P, json.dumps(structure))).lastrowid
    conn.commit()
    conn.close()

    ui.page.evaluate("""async id => {
        await ReportingManager.loadReport(id);
        // Render both panes explicitly in case the generator view is not mounted.
        document.getElementById('workspaceItems').innerHTML = ReportingManager.renderWorkspaceItems();
        document.getElementById('reportPreview').innerHTML = ReportingManager.renderPreview();
        // Expand a writeup's title editor, which has its own handlers.
        const writeup = ReportingManager.workspaceItems.find(i => i.type === 'writeup');
        ReportingManager._expandedWriteupId = writeup.id;
        document.getElementById('xssScratch').innerHTML = ReportingManager.renderWorkspaceItems();
    }""", report_id)
    assert ui.page.evaluate('() => ReportingManager.workspaceItems.length') == len(structure)
    _assert_clean(ui.page)


# ------------------------------------------------------------------ attack map, admin, commands, clients

def test_attack_map_reference(ui):
    ui.page.evaluate("""p => {
        AttackMapEditor.nodes = [{ id: 1, node_type: 'evidence_ref', label: p, ref_type: p, ref_id: p, properties: {} }];
        AttackMapEditor.selectedNodeId = 1;
        AttackMapEditor.renderPropertiesPanel();
    }""", P)
    _assert_clean(ui.page)


def test_admin_engagement_list_and_delete_receives_the_name(ui):
    conn = ui.db()
    eng_id = conn.execute('INSERT INTO engagements (name, client_name) VALUES (?, ?)', (P, P)).lastrowid
    conn.commit()
    conn.close()
    ui.page.evaluate('() => AdminPanel.loadEngagementsList()')
    _assert_clean(ui.page)
    got = ui.page.evaluate("""id => {
        let got = null;
        const original = AdminPanel.confirmDeleteEngagement;
        AdminPanel.confirmDeleteEngagement = (eid, name) => { got = [eid, name]; };
        document.querySelector(`[data-action="confirm-delete-engagement"][data-engagement-id="${id}"]`).click();
        AdminPanel.confirmDeleteEngagement = original;
        return got;
    }""", eng_id)
    assert got == [eng_id, P]


def test_command_categories(ui):
    got = ui.page.evaluate("""p => {
        CommandManager.categories = [{ name: p, count: p }];
        CommandManager.renderCategoryTabs();
        let got = null;
        const original = CommandManager.filterByCategory;
        CommandManager.filterByCategory = c => { got = c; };
        document.querySelector('#commandCategories [data-action="filter-command-category"]').click();
        CommandManager.filterByCategory = original;
        return got;
    }""", P)
    assert got == P
    _assert_clean(ui.page)


def test_client_website_link(ui):
    hrefs = ui.page.evaluate("""p => {
        ClientManager.clients = [{ id: 1, name: p, website: 'javascript:window.__xss.push(1)' },
                                 { id: 2, name: 'ok', website: 'https://example.com' }];
        ClientManager.renderClientsList();
        return [...document.querySelectorAll('#clientsList a[href]')].map(a => a.getAttribute('href'));
    }""", P)
    assert hrefs == ['#', 'https://example.com']
    _assert_clean(ui.page)


# ------------------------------------------------------------------ shell one-liners, test plans

def test_oneliner_card_and_copy_receives_the_raw_command(ui):
    got = ui.page.evaluate("""p => {
        ShellOneLinersManager.state.subcategories = { x: [{ name: p, count: 1 }] };
        ShellOneLinersManager.state.activeCategory = 'x';
        ShellOneLinersManager.renderSubcategoryFilter();
        const scratch = document.getElementById('xssScratch');
        scratch.innerHTML = ShellOneLinersManager.renderOnelinerCard({ name: p, description: p, command: p });
        const got = {};
        const copy = ShellOneLinersManager.copyCommand, filter = ShellOneLinersManager.filterBySubcategory;
        ShellOneLinersManager.copyCommand = c => { got.copied = c; };
        ShellOneLinersManager.filterBySubcategory = s => { got.sub = s; };
        scratch.querySelector('[data-action="copy-oneliner"]').click();
        document.querySelector('#shellSubcategoryFilter [data-action="filter-oneliner-subcategory"]').click();
        ShellOneLinersManager.copyCommand = copy;
        ShellOneLinersManager.filterBySubcategory = filter;
        return got;
    }""", P)
    assert got == {'copied': P, 'sub': P}
    _assert_clean(ui.page)


def test_test_plan_item_modal_uses_the_raw_command(ui):
    value = ui.page.evaluate("""p => {
        TestPlansManager.showEditItemModal(1, { id: 1, atomic_id: 5, atomic_test_name: p, executor_command: p,
                                                custom_name: p, custom_command: p, notes: p, technique_id: p });
        document.querySelector('#editItemModal [data-action="use-original-command"]').click();
        return document.getElementById('editItemCommand').value;
    }""", P)
    assert value == P
    _assert_clean(ui.page)


# ------------------------------------------------------------------ retest: H-13

def _hostile_vuln():
    """A vulnerability record with the payload in every field the tab reads."""
    fields = ('plugin_id', 'plugin_name', 'plugin_family', 'port', 'service', 'protocol', 'risk_factor',
              'synopsis', 'description', 'solution', 'plugin_output', 'cvss_base_score', 'cvss_vector',
              'exploit_available', 'confidence', 'location', 'name', 'id', 'evidence_title', 'source_tool')
    vuln = {f: P for f in fields}
    vuln.update(severity=3, cves=[P], is_engagement_finding=True, include_in_report=P)
    return vuln


def test_host_vulnerabilities_tab_escapes_every_field(ui):
    """H-13: the tab builds its list from evidence metadata JSON, which an editor or a scan file controls."""
    conn = ui.db()
    host_id = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.0.0.9')", (ENGAGEMENT_A,)).lastrowid
    nessus = {'tool': 'nessus', 'hosts': [{'ip': '10.0.0.9', 'vulnerabilities': [_hostile_vuln()]}]}
    burp = {'tool': 'burp', 'issues': [{**_hostile_vuln(), 'host': f'http://10.0.0.9:{P}', 'severity': 'High',
                                        'issue_detail': P, 'remediation': P, 'path': P}]}
    for meta in (nessus, burp):
        conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title, metadata) VALUES (?, 'tool_output', ?, ?)",
                     (ENGAGEMENT_A, P, json.dumps(meta)))
    conn.execute("INSERT INTO engagement_findings (engagement_id, title, ip_address, criticality, cvss_score, "
                 "finding_content, remediation_content) VALUES (?, ?, '10.0.0.9', ?, ?, ?, ?)",
                 (ENGAGEMENT_A, P, P, P, P, P))
    conn.commit()
    conn.close()

    ui.page.evaluate("""async hostId => {
        if (!document.getElementById('vulnerabilitiesList')) {
            const div = document.createElement('div');
            div.id = 'vulnerabilitiesList';
            document.body.appendChild(div);
        }
        AppState.activeEngagement = AppState.activeEngagement || { id: %d };
        HostManager.hosts = [{ id: hostId, ip: '10.0.0.9' }];
        await HostManager.loadVulnerabilities(hostId);
    }""" % ENGAGEMENT_A, host_id)
    assert ui.page.evaluate('() => HostManager.currentVulnerabilities.length') == 3
    _assert_clean(ui.page)
    # A metadata record cannot pose as an editable engagement finding
    assert ui.page.evaluate("""() => HostManager.currentVulnerabilities
        .filter(v => v.is_engagement_finding).every(v => Number.isInteger(v.id))""")


# ------------------------------------------------------------------ retest: H-14

def test_host_credentials_table_escapes_password_type(ui):
    ui.page.evaluate("""p => {
        if (!document.getElementById('credentialsTableBody')) {
            const t = document.createElement('table');
            t.innerHTML = '<tbody id="credentialsTableBody"></tbody>';
            document.body.appendChild(t);
        }
        HostManager.currentCredentials = [
            { id: 1, username: p, has_secret: true, password_type: p, hash_type: p, service: p, notes: p },
            { id: 2, username: p, has_secret: true, password_type: 'hash', hash_type: p, service: p, notes: p },
        ];
        HostManager.renderCredentials();
    }""", P)
    _assert_clean(ui.page)


def test_note_trees_escape_stored_ordering_fields(ui):
    """H-15: rows stored before validation (or written directly) keep a text sort_order."""
    conn = ui.db()
    host_id = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.0.0.15')", (ENGAGEMENT_A,)).lastrowid
    for table, scope in (('host_notes', host_id), ('engagement_notes', ENGAGEMENT_A)):
        column = 'host_id' if table == 'host_notes' else 'engagement_id'
        root = conn.execute(f'INSERT INTO {table} ({column}, content, title, sort_order) VALUES (?, ?, ?, ?)',
                            (scope, P, P, P)).lastrowid
        conn.execute(f'INSERT INTO {table} ({column}, content, title, parent_id, sort_order) VALUES (?, ?, ?, ?, ?)',
                     (scope, P, P, root, P))
    conn.commit()
    conn.close()
    count = ui.page.evaluate("""async ([hostId, engagementId]) => {
        const views = [
            ['xssHostTree', API.hosts, 'host', hostId],
            ['xssEngagementTree', API.engagements, 'engagement', engagementId],
        ];
        let items = 0;
        for (const [id, api, noun, scope] of views) {
            const div = document.createElement('div');
            div.id = id;
            document.body.appendChild(div);
            const view = new NotesTreeView({ containerId: id, toolbarId: id + 'Toolbar', editorPaneId: id + 'Pane',
                                             api, apiNoun: noun, scopeId: () => scope });
            await view.refresh();
            items += div.querySelectorAll('.notes-tree-item').length;
        }
        return items;
    }""", [host_id, ENGAGEMENT_A])
    assert count == 4
    _assert_clean(ui.page)


# The breakdown splits the vector on '/' and ':', so this payload uses neither.
CVSS_P = '<img src=x data-pwn=1 onerror="window.__xss.push(\'cvss\')">'


def test_cvss_card_breakdown_escapes_vector_values(ui):
    """H-16: a CVSS card's vector values (and the editor's score) render as text."""
    vectors = [f'CVSS:3.1/AV:{CVSS_P}/AC:L', f'CVSS:3.1/{CVSS_P}:N', 'CVSS:3.1/constructor:N/__proto__:x/AV:N']
    rendered = ui.page.evaluate("""([vectors, p]) => {
        const out = [];
        for (const vector of vectors) {
            out.push(ReportingManager.renderCvssBreakdown(vector));
            ReportingManager.workspaceItems = [{ id: 'c1', type: 'format_tool', format_tool_id: 'cvsscard',
                                                 title: 'c', toolData: { score: p, vector } }];
            document.getElementById('reportPreview').innerHTML = ReportingManager.renderPreview();
            ReportingManager.editingToolData = { score: p, vector };
            document.getElementById('xssScratch').innerHTML = ReportingManager.getEditorBodyForTool('cvsscard');
        }
        document.getElementById('workspaceItems').innerHTML = out.join('');
        return out;
    }""", [vectors, P])
    _assert_clean(ui.page)
    assert 'Attack Complexity' in rendered[0] and 'Network' in rendered[2]


def test_import_fed_fields_render_as_text(ui):
    """H-17: values an old import could store (status, dates, types, criticality, CVSS) render as text."""
    ui.page.evaluate("""async p => {
        for (const id of ['engagementsGrid', 'evidenceList', 'engagementFindingsList']) {
            if (!document.getElementById(id)) {
                const div = document.createElement('div');
                div.id = id;
                document.body.appendChild(div);
            }
        }
        if (!document.getElementById('engagementCredentialsTableBody')) {
            const table = document.createElement('table');
            table.innerHTML = '<tbody id="engagementCredentialsTableBody"></tbody>';
            document.body.appendChild(table);
        }
        await renderEngagementsGrid([{ id: 1, name: 'n', status: p, start_date: p, end_date: p }]);
        const ev = { id: 1, title: 't', content: 'c', evidence_type: p, tags: '' };
        renderEvidenceList([ev]);
        HostManager.renderEvidenceDetails([ev]);
        HostManager.engagementCredentials = [{ id: 1, username: 'u', credential_type: p }];
        HostManager.renderEngagementCredentials();
        HostManager.engagementFindings = [{ id: 1, title: 't', criticality: p, cvss_score: p }];
        HostManager.renderEngagementFindings();
        ReportingManager.engagementFindings = [{ id: 1, title: 't', criticality: p }];
        ReportingManager.writeups = [{ id: 1, name: 'w', writeup_type: 'finding', criticality: p, cvss_score: p }];
        document.getElementById('xssScratch').innerHTML = ReportingManager.renderSourceFindings()
            + ReportingManager.renderSourceWriteups() + ReportingManager.renderWriteupsList();
    }""", P)
    _assert_clean(ui.page)


def test_oneliner_list_escapes_the_subcategory_heading(ui):
    """L-20: the group heading is the stored subcategory; it renders as text, any name groups."""
    headings = ui.page.evaluate("""p => {
        if (!document.getElementById('shellOnelinersList')) {
            const div = document.createElement('div');
            div.id = 'shellOnelinersList';
            document.body.appendChild(div);
        }
        ShellOneLinersManager.state.loading = false;
        ShellOneLinersManager.renderOnelinersList([
            { name: 'a', command: 'id', subcategory: p },
            { name: 'b', command: 'id', subcategory: '__proto__' },
            { name: 'c', command: 'id', subcategory: 'constructor' },
            { name: 'd', command: 'id' },
        ]);
        return [...document.querySelectorAll('#shellOnelinersList .shell-group-title')].map(h => h.textContent);
    }""", P)
    assert headings == [P, '__proto__', 'constructor', 'other']
    _assert_clean(ui.page)


# ------------------------------------------------------------------ full sweep
# Every free-text field is stored with P through the real API (so only what the
# server accepts is stored), then each view is opened through the app's own
# loaders and checked. Fields with a format (emails, dates, enums, numbers) get
# valid values: the server rejects anything else. A view must show P as text,
# so a view that silently failed to render does not pass.

EMAIL = 'sweep@example.com'
SHORT_P = 'u"\'><img src=x data-pwn=1 onerror="window.__xss.push(\'u\')">'      # for 100-character fields
FORMAT_TOOLS = [
    ('sectionheader', {'text': P, 'level': 'h2', 'numbered': True, 'number': P}),
    ('textblock', {'content': P}), ('quote', {'text': P, 'attribution': P}),
    ('bulletlist', {'items': [P]}), ('numberedlist', {'items': [P]}),
    ('checklist', {'title': P, 'items': [{'text': P, 'checked': True}]}),
    ('codeblock', {'title': P, 'language': P, 'code': P}), ('commandoutput', {'command': P, 'output': P}),
    ('alertbox', {'type': 'info', 'content': P}), ('keyfinding', {'title': P, 'content': P}),
    ('evidenceblock', {'caption': P, 'description': P, 'impact': P}),
    ('imageplaceholder', {'caption': P, 'width': '50%'}),
    ('twocolumn', {'leftTitle': P, 'leftContent': P, 'rightTitle': P, 'rightContent': P}),
    ('timeline', {'steps': [{'time': P, 'title': P, 'description': P}]}),
    ('riskmatrix', {'size': 3, 'highlighted': '0-0'}), ('cvsscard', {'score': 9.8, 'vector': P}),
]


def _ok(resp):
    assert resp.status_code in (200, 201), (resp.request.path, resp.status_code, resp.get_json(silent=True))
    return resp.get_json()


@pytest.fixture
def swept(ui):
    """Store P in every free-text field the API accepts, for engagement A."""
    c = ui.client_for('admin', active_engagement=ENGAGEMENT_A)
    eng = f'/api/engagements/{ENGAGEMENT_A}'
    ids = {}

    client = _ok(c.post('/api/clients', json={'name': P, 'admin_contact_name': P, 'admin_contact_email': EMAIL,
                                              'admin_contact_phone': P, 'technical_contact_name': P,
                                              'technical_contact_email': EMAIL, 'technical_contact_phone': P,
                                              'address': P, 'website': P, 'notes': P}))
    _ok(c.put(eng, json={'name': P, 'client_name': P, 'short_name': P, 'description': P, 'tags': P,
                         'contact_name': P, 'contact_phone': P, 'contact_email': EMAIL, 'start_date': '2026-01-01',
                         'end_date': '2026-02-01', 'client_id': client['id']}))
    _ok(c.post('/api/teams', json={'name': P, 'description': P}))
    user = _ok(c.post('/api/users', json={'username': SHORT_P, 'email': EMAIL, 'full_name': P,
                                          'password': 'Sweep-Passphrase-123', 'role': 'tester'}))
    _ok(c.post(f'{eng}/members', json={'user_id': user['id'], 'role': 'editor'}))

    host = _ok(c.post('/api/hosts', json={'ip': '10.0.0.50', 'hostname': P, 'os': P, 'notes': P}))
    ids['host'] = h = host['id']
    _ok(c.post(f'/api/hosts/{h}/ports', json={'port': 443, 'protocol': 'tcp', 'state': 'open',
                                              'service': P, 'version': P}))
    _ok(c.post(f'/api/hosts/{h}/credentials', json={'username': P, 'password': P, 'password_type': 'hash',
                                                    'hash_type': P, 'service': P, 'notes': P}))
    ids['host_note'] = _ok(c.post(f'/api/hosts/{h}/notes', json={'title': P, 'content': P}))['id']
    ids['eng_note'] = _ok(c.post(f'{eng}/notes', json={'title': P, 'content': P}))['id']
    _ok(c.post(f'{eng}/credentials', json={'username': P, 'password_or_hash': P, 'credential_type': 'ntlm',
                                           'description': P}))
    _ok(c.post(f'{eng}/terminal-dumps', json={'title': P, 'content': P, 'session_datetime': P}))
    ids['finding'] = _ok(c.post(f'{eng}/findings', json={
        'title': P, 'ip_address': P, 'hostname': P, 'criticality': 'high', 'cvss_score': 9.1,
        'finding_content': P, 'remediation_content': P}))['id']
    evidence = _ok(c.post('/api/evidence', json={'evidence_type': 'note', 'title': P, 'content': P, 'tags': P,
                                                 'metadata': json.dumps({'tool': P, 'note': P})}))
    _ok(c.post(f'/api/hosts/{h}/evidence', json={'evidence_id': evidence['id']}))
    _ok(c.post('/api/filters', json={'name': P, 'description': P,
                                     'filter_json': {'search_query': P, 'tags': [P]}}))

    writeup = _ok(c.post('/api/reporting/writeups', json={
        'name': P, 'category': P, 'criticality': 'high', 'cvss_score': 7.5, 'description': P,
        'remediation': P, 'tags': P, 'writeup_type': 'finding'}))
    _ok(c.post('/api/reporting/writeups', json={'name': P, 'category': P, 'description': P, 'tags': P,
                                                'writeup_type': 'narrative'}))
    structure = [{'id': f'f{i}', 'type': 'format_tool', 'format_tool_id': tool, 'title': P, 'toolData': data}
                 for i, (tool, data) in enumerate(FORMAT_TOOLS)]
    structure.append({'id': 'tbl', 'type': 'format_tool', 'format_tool_id': 'table', 'title': P, 'toolData': {},
                      'tableData': {'headers': [P], 'rows': [[P]]}})
    structure += [{'id': 'ef', 'type': 'engagement_finding', 'source_id': ids['finding'], 'customizations': {}},
                  {'id': 'wu', 'type': 'writeup', 'source_id': writeup['id'], 'customizations': {}}]
    ids['report'] = _ok(c.post('/api/reporting/reports', json={'name': P, 'structure': structure}))['id']

    _ok(c.post('/api/commands', json={'name': P, 'category': 'Recon', 'command': P, 'description': P}))
    _ok(c.post('/api/shell-oneliners/admin', json={'name': P, 'category': 'reverse_shells', 'subcategory': P,
                                                   'command': P, 'description': P}))

    attack_map = _ok(c.post('/api/attack-maps', json={'name': P, 'description': P}))
    ids['map'] = m = attack_map['id']
    a = _ok(c.post(f'/api/attack-maps/{m}/nodes', json={'node_type': 'tactic', 'label': P, 'x': 50, 'y': 50,
                                                        'properties': {'notes': P, 'technique': P}}))
    b = _ok(c.post(f'/api/attack-maps/{m}/nodes', json={'node_type': 'exploit', 'label': P, 'x': 300, 'y': 50}))
    ids['node'] = a['id']
    _ok(c.post(f'/api/attack-maps/{m}/edges', json={'source_node_id': a['id'], 'target_node_id': b['id'],
                                                    'label': P}))

    plan = _ok(c.post('/api/testplans/plans', json={'name': P, 'description': P, 'tags': P,
                                                    'target_platform': 'windows'}))
    plan_id = plan.get('id') or plan.get('plan', {}).get('id')
    _ok(c.post(f'/api/testplans/plans/{plan_id}/items', json={'custom_name': P, 'custom_command': P,
                                                               'custom_platform': 'windows', 'notes': P}))
    execution = _ok(c.post('/api/testplans/executions/start', json={'plan_id': plan_id, 'host_id': h}))
    for ex in execution.get('executions', [execution]):
        if ex.get('id'):
            _ok(c.put(f"/api/testplans/executions/{ex['id']}", json={
                'execution_output': P, 'execution_notes': P, 'detected_by': P}))
    layer = json.dumps({'name': P, 'description': P, 'domain': 'enterprise-attack',
                        'techniques': [{'techniqueID': 'T1059', 'comment': P}]})
    _ok(c.post('/api/testplans/layers/import', data={'file': (io.BytesIO(layer.encode()), 'layer.json')},
               content_type='multipart/form-data'))
    ui.ids = ids
    return ui


SHOWN = """([root, payloads]) => {
    // The start of a payload in the view's text (SVG labels and titles too; charts and cards
    // may truncate it, and editors split it across spans) or in a form value.
    const scope = document.querySelector(root);
    const prefixes = payloads.map(p => p.slice(0, 12));
    const text = scope.textContent;
    let n = prefixes.reduce((sum, prefix) => sum + text.split(prefix).length - 1, 0);
    for (const el of scope.querySelectorAll('input, textarea')) if (prefixes.some(x => el.value.includes(x))) n++;
    return n;
}"""

# name -> (section checked for P, async JS run with ids); each opens a view through the app's loaders.
VIEWS = {
    'engagements': ('#section-engagements', """async () => { switchSection('engagements'); await loadEngagements(); }"""),
    'dashboard': ('#section-dashboard', """async () => { switchSection('dashboard'); await Dashboard.load(); }"""),
    'general': ('#section-hosts', """async ids => {
        await loadActiveEngagement();
        switchSection('general');
        for (const tab of ['notes', 'credentials', 'terminal', 'findings']) await HostManager.switchGeneralTab(tab);
        await HostManager.switchGeneralTab('notes');
        await HostManager.loadEngagementNotes();
        document.querySelector('#engagementNotesList .notes-tree-row')?.click();
    }"""),
    'hosts': ('#section-hosts', """async ids => {
        switchSection('hosts');
        await HostManager.loadHosts();
        await HostManager.loadSavedFilters();
        await HostManager.selectHost(ids.host);
        for (const tab of ['notes', 'ports', 'findings', 'credentials']) HostManager.switchHostTab(tab);
        await HostManager.loadNotes(ids.host);
        document.querySelector('#notesList .notes-tree-row')?.click();
    }"""),
    'portgrid': ('#section-portgrid', """async () => { switchSection('portgrid'); await HostManager.loadPortGridPage(); }"""),
    'tools': ('#section-tools', """async () => {
        switchSection('tools');
        for (const [tool, manager, subs] of [['command', 'CommandHubManager', ['shells', 'commands', 'msfvenom']],
                                             ['calculators', 'CalculatorsManager', ['cvss', 'subnet']],
                                             ['decoders', 'DecodersManager', ['jwt', 'powershell']],
                                             ['data', null, []]]) {
            ToolsManager.switchTool(tool);
            for (const sub of subs) { window[manager].switchSubTool(sub); await new Promise(r => setTimeout(r, 150)); }
        }
        ToolsManager.switchTool('command');
        CommandHubManager.switchSubTool('shells');
        await ShellOneLinersManager.init();
        CommandHubManager.switchSubTool('commands');
        await CommandManager.init();
    }"""),
    'attack map': ('#section-tools', """async ids => {
        switchSection('tools');
        ToolsManager.switchTool('attackmaps');
        await new Promise(r => setTimeout(r, 300));
        await AttackMapEditor.loadMap(ids.map);
        await AttackMapEditor.selectNode(ids.node);
    }"""),
    'reporting': ('#section-reporting', """async ids => {
        switchSection('reporting');
        await ReportingManager.init();
        await ReportingManager.switchTab('writeups');
        await ReportingManager.switchTab('generation');
        await ReportingManager.loadReport(ids.report);
        await ReportingManager.switchTab('templates');
        await ReportingManager.switchTab('generation');
    }"""),
    'test plans': ('#section-testplans', """async () => {
        switchSection('testplans');
        await TestPlansManager.init();
        for (const tab of ['plans', 'executions', 'navigator', 'atomics', 'plans']) await TestPlansManager.switchTab(tab);
    }"""),
    'admin': ('#section-admin', """async () => {
        switchSection('admin');
        await AdminPanel.init();
        for (const tab of ['settings', 'users', 'teams', 'clients', 'shells', 'engagements', 'users']) {
            await AdminPanel.switchTab(tab);
            await new Promise(r => setTimeout(r, 200));
        }
    }"""),
    # No dashboard view holds the members list yet; its renderer still runs against a container.
    'members': ('#membersList', """async () => {
        const div = document.createElement('div');
        div.id = 'membersList';
        document.body.appendChild(div);
        await UserManager.loadEngagementMembers(AppState.activeEngagement.id);
    }"""),
}


@pytest.mark.parametrize('view', VIEWS)
def test_every_view_renders_stored_values_as_text(swept, view):
    page = swept.page
    root, script = VIEWS[view]
    page.evaluate(script, swept.ids)
    page.wait_for_timeout(400)                 # renders scheduled with setTimeout, image errors
    _assert_clean(page)
    assert page.evaluate(SHOWN, [root, [P, SHORT_P]]) > 0, \
        f'{view}: the stored value was not rendered: ' + page.evaluate('r => document.querySelector(r)?.innerText.slice(0, 600)', root)


@pytest.mark.parametrize('path', ['/note/new?type=engagement&note_id={eng_note}',
                                  '/note/new?type=host&host_id={host}&note_id={host_note}',
                                  '/finding/new?finding_id={finding}'])
def test_editor_pages_render_stored_values_as_text(swept, path):
    page = swept.page
    page.add_init_script('window.__xss = [];')
    page.goto(swept.base + path.format(**swept.ids))
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(300)
    _assert_clean(page)
    assert page.evaluate(SHOWN, ['body', [P, SHORT_P]]) > 0, page.evaluate('() => document.body.innerText.slice(0, 600)')


# ------------------------------------------------------------------ form checks

def test_encrypt_database_form_applies_the_passphrase_policy(ui):
    """M-12: the Admin > Settings form refuses a weak passphrase before sending it."""
    got = ui.page.evaluate("""async () => {
        AdminPanel.activeTab = 'settings';
        document.getElementById('xssScratch').innerHTML = AdminPanel.renderSettingsTab();
        const sent = [], toasts = [];
        const enable = API.admin.enableEncryption, toast = window.showToast;
        API.admin.enableEncryption = async p => { sent.push(p); return { message: 'ok' }; };
        window.showToast = (m, kind) => toasts.push(kind);
        AdminPanel.loadEncryptionStatus = async () => {};
        try {
            for (const p of ['', 'short-Pass1', 'alllowercase-123', 'ALLUPPERCASE-123', 'No-Digits-Here-At-All',
                             'Enable-Passphrase-123', 'Élan-passphrase-1']) {
                document.getElementById('encryptionPassword').value = p;
                await AdminPanel.confirmEnableEncryption();
            }
        } finally {
            API.admin.enableEncryption = enable;
            window.showToast = toast;
        }
        return { sent, toasts };
    }""")
    assert got['sent'] == ['Enable-Passphrase-123', 'Élan-passphrase-1']
    assert got['toasts'] == ['error'] * 5 + ['success'] * 2

"""L-11 and L-12: generated-script defaults, download names, templates,
XML parsing, the password policy in the UI and docs, and input size limits.
"""

import io
import json
import pathlib
import shutil
import subprocess

import pytest

from tests.conftest import ENGAGEMENT_A
from utils.script_generator import _bash_prompt_block, generate_script

ROOT = pathlib.Path(__file__).resolve().parent.parent
needs_bash = pytest.mark.skipif(not shutil.which('bash'), reason='bash not available')


# ------------------------------------------------------------------ L-11: bash defaults

@needs_bash
@pytest.mark.parametrize('default', ["a b $(touch {marker})", "it's `touch {marker}`", '"quoted" ${{HOME}}'])
def test_bash_default_is_used_literally(tmp_path, default):
    marker = tmp_path / 'ran'
    value = default.format(marker=marker)
    block = _bash_prompt_block([{'name': 'arg', 'description': '', 'type': 'string', 'default': value}], indent='')
    out = subprocess.run(['bash', '-c', block + '\nprintf "<<%s>>" "$arg"'], input='\n',
                         capture_output=True, text=True, timeout=10)
    assert out.stdout.split('<<', 1)[1].rsplit('>>', 1)[0] == value
    assert not marker.exists()


@needs_bash
def test_bash_typed_input_replaces_the_default():
    block = _bash_prompt_block([{'name': 'arg', 'description': '', 'type': 'string', 'default': 'd'}], indent='')
    out = subprocess.run(['bash', '-c', block + '\nprintf "<<%s>>" "$arg"'], input='typed\n',
                         capture_output=True, text=True, timeout=10)
    assert out.stdout.split('<<', 1)[1].rsplit('>>', 1)[0] == 'typed'


ITEM = {'id': 1, 'enabled': 1, 'technique_id': 'T1059', 'atomic_test_name': 'Echo', 'atomic_id': 5,
        'executor_command': 'echo #{p}', 'executor_cleanup': None, 'supported_platforms': '["linux", "windows"]',
        'input_arguments': json.dumps({'p': {'description': 'd', 'type': 'string', 'default': 'library-default'}}),
        'elevation_required': 0}


@pytest.mark.parametrize('platform', ['bash', 'powershell'])
def test_plan_item_input_overrides_become_the_default(platform):
    item = {**ITEM, 'input_overrides': json.dumps({'p': 'plan-override', 'unknown': 'ignored'})}
    script = generate_script({'name': 'P', 'description': ''}, [item], platform)
    assert 'plan-override' in script and 'library-default' not in script
    assert 'ignored' not in script


def test_malformed_overrides_are_ignored():
    item = {**ITEM, 'input_overrides': '{not json'}
    assert 'library-default' in generate_script({'name': 'P', 'description': ''}, [item], 'bash')


# ------------------------------------------------------------------ L-12: download names

@pytest.mark.parametrize('name', ['Q3 "final".pdf', 'r\r\nSet-Cookie: x=1', 'Rapport été/../x', ''])
def test_attachment_disposition_is_safe(name):
    from utils.security_headers import attachment_disposition
    value = attachment_disposition(name, fallback='report')
    assert '\r' not in value and '\n' not in value
    plain = value.split('filename="', 1)[1].split('"', 1)[0]
    assert plain and all(c.isalnum() or c in '._- ' for c in plain)
    assert "filename*=UTF-8''" in value


def test_report_export_uses_a_safe_filename(live_app):
    conn = live_app.db()
    report_id = conn.execute("INSERT INTO reports (engagement_id, name, structure) VALUES (?, ?, '[]')",
                             (ENGAGEMENT_A, 'Q3 "final"\r\nX-Injected: 1 été')).lastrowid
    conn.commit()
    conn.close()
    resp = live_app.client_for('viewer', active_engagement=ENGAGEMENT_A).get(
        f'/api/reporting/reports/{report_id}/export?format=markdown')
    assert resp.status_code == 200
    disposition = resp.headers['Content-Disposition']
    assert 'X-Injected' not in resp.headers and disposition.count('"') == 2
    assert "filename*=UTF-8''" in disposition and '%C3%A9' in disposition


# ------------------------------------------------------------------ L-12: templates and XML

def test_markdown_templates_render_in_a_sandbox():
    source = (ROOT / 'routes/templates.py').read_text()
    assert 'SandboxedEnvironment' in source and 'Template(template_content)' not in source


@pytest.mark.parametrize('name', ['..', 'a.b', 'x%2F..'])
def test_template_names_are_validated(live_app, name):
    resp = live_app.client_for('owner', active_engagement=ENGAGEMENT_A).get(
        f'/api/engagements/{ENGAGEMENT_A}/export/template/{name}')
    assert resp.status_code in (400, 404)


def test_nmap_parser_refuses_entity_expansion(tmp_path):
    from utils.parsers.nmap_parser import NmapToolParser
    bomb = tmp_path / 'scan.xml'
    bomb.write_text('<?xml version="1.0"?><!DOCTYPE nmaprun [<!ENTITY a "aaaaaaaaaa">'
                    '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><nmaprun>&b;</nmaprun>')
    assert NmapToolParser(str(bomb)).validate() is False
    source = (ROOT / 'utils/parsers/nmap_parser.py').read_text()
    assert 'xml.etree.ElementTree' not in source


# ------------------------------------------------------------------ L-12: password policy in UI and docs

def test_ui_and_docs_state_the_real_password_minimum():
    setup = (ROOT / 'templates/setup.html').read_text()
    assert 'minlength="8"' not in setup and 'minlength="12"' in setup
    assert 'length < 8' not in (ROOT / 'static/js/auth.js').read_text()
    for doc in ('README.md', 'CLAUDE.md', 'docs/getting-started/first-time-setup.md'):
        text = (ROOT / doc).read_text()
        assert 'at least 8 characters' not in text and '8 characters long' not in text, doc


# ------------------------------------------------------------------ L-12: input limits

def _import(live, payload):
    client = live.client_for('editor', active_engagement=ENGAGEMENT_A)
    return client.post('/api/engagements/import', data={
        'file': (io.BytesIO(json.dumps(payload).encode()), 'export.json')}, content_type='multipart/form-data')


BASE = {'export_metadata': {'version': '1.0'}, 'engagement': {'name': 'R'}}


@pytest.mark.parametrize('payload', [
    [1, 2, 3],
    {**BASE, 'engagement': 'not an object'},
    {**BASE, 'hosts': {'not': 'a list'}},
    {**BASE, 'evidence': ['not an object']},
])
def test_import_rejects_malformed_shapes(live_app, payload):
    assert _import(live_app, payload).status_code == 400


def test_import_caps_collection_sizes(live_app, monkeypatch):
    import routes.engagements as engagements
    monkeypatch.setattr(engagements, 'MAX_IMPORT_ITEMS', 3)
    resp = _import(live_app, {**BASE, 'hosts': [{'id': i, 'ip': f'10.0.0.{i}'} for i in range(4)]})
    assert resp.status_code == 400 and 'too many' in resp.get_json()['error'].lower()


@pytest.mark.parametrize('structure', [{'not': 'a list'}, ['not an object']])
def test_report_structure_must_be_a_list_of_items(live_app, structure):
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    assert client.post('/api/reporting/reports', json={'name': 'R', 'structure': structure}).status_code == 400


def test_report_structure_item_count_is_capped(live_app, monkeypatch):
    import routes.reporting as reporting
    monkeypatch.setattr(reporting, 'MAX_REPORT_ITEMS', 2)
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    items = [{'id': f'i{n}', 'type': 'format_tool', 'format_tool_id': 'spacer'} for n in range(3)]
    assert client.post('/api/reporting/reports', json={'name': 'R', 'structure': items}).status_code == 400
    created = client.post('/api/reporting/reports', json={'name': 'R', 'structure': items[:2]})
    assert created.status_code == 201
    report_id = created.get_json()['id']
    assert client.put(f'/api/reporting/reports/{report_id}', json={'structure': items}).status_code == 400

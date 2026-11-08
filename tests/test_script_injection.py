"""H-12: plan fields cannot inject code into generated test scripts.

A plan's name and description, and item names, reach the generated script
in comments, banners and messages. A newline, $(...), backticks or (in
PowerShell) the Unicode quote characters must not end a comment or string.
"""

import os
import re
import shutil
import subprocess
import tempfile

import pytest

from utils.script_generator import (_powershell_escape_dquoted, _powershell_escape_squoted,
                                    generate_script)

needs_bash = pytest.mark.skipif(not shutil.which('bash'), reason='bash not available')

ITEM = {'id': 1, 'enabled': 1, 'technique_id': 'T1059', 'atomic_test_name': 'Echo',
        'executor_command': 'echo hi', 'executor_cleanup': None, 'supported_platforms': '["linux", "windows"]',
        'input_arguments': None, 'elevation_required': 0}

# Unicode quotes PowerShell treats as delimiters.
PS_DOUBLE = '“”„'
PS_SINGLE = '‘’‚‛'


@pytest.fixture
def markers(tmp_path):
    return {k: tmp_path / k for k in ('newline_name', 'newline_desc', 'subst', 'backtick', 'item')}


def _bash_payload_script(markers):
    plan = {
        'name': f"Recon\ntouch {markers['newline_name']}\n$(touch {markers['subst']})`touch {markers['backtick']}`",
        'description': f"desc\r\ntouch {markers['newline_desc']}",
    }
    item = {**ITEM, 'custom_name': f"x\n$(touch {markers['item']})"}
    return generate_script(plan, [item], 'bash')


def _run(script, stdin='', env=None, snippet=None):
    with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as fh:
        fh.write(script)
    try:
        full_env = {**os.environ, 'TERM': 'dumb'}
        full_env.pop('PTVAULT_AUTHORIZED_HOST', None)
        full_env.update(env or {})
        cmd = ['bash', fh.name] if snippet is None else ['bash', '-c', f'source "{fh.name}" 2>/dev/null; {snippet}']
        return subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=full_env, timeout=20)
    finally:
        os.unlink(fh.name)


@needs_bash
def test_bash_script_parses(markers):
    script = _bash_payload_script(markers)
    with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as fh:
        fh.write(script)
    try:
        assert subprocess.run(['bash', '-n', fh.name], capture_output=True).returncode == 0
    finally:
        os.unlink(fh.name)


@needs_bash
def test_bash_header_cannot_run_code_before_the_hostname_gate(markers):
    result = _run(_bash_payload_script(markers), stdin='not-this-host\n')
    assert result.returncode == 1
    assert not any(p.exists() for p in markers.values()), [p.name for p in markers.values() if p.exists()]


@needs_bash
def test_bash_menus_print_but_do_not_run_the_plan_name(markers):
    script = _bash_payload_script(markers)
    body = script.rsplit('confirm_authorization\nselect_execution_mode', 1)[0]
    for snippet in ('show_menu', 'select_execution_mode'):  # 'q' quits the mode menu
        _run(body, stdin='q\n', snippet=snippet)
    assert not any(p.exists() for p in markers.values()), [p.name for p in markers.values() if p.exists()]


def test_bash_comments_stay_on_one_line():
    script = generate_script({'name': 'a\nb', 'description': 'c\r\nd'}, [ITEM], 'bash')
    assert '# PTVault Test Plan: a b' in script
    assert '# Description: c d' in script


# --------------------------------------------------------------- PowerShell

def test_powershell_comments_stay_on_one_line():
    script = generate_script({'name': 'a\nWrite-Output pwned', 'description': 'c\r\nd'}, [ITEM], 'powershell')
    assert '\nWrite-Output pwned' not in script
    assert '# Description: c d' in script


@pytest.mark.parametrize('quote', list(PS_DOUBLE))
def test_powershell_double_quoted_escape_handles_unicode_quotes(quote):
    escaped = _powershell_escape_dquoted(f'a{quote}; Write-Output pwned; {quote}b')
    assert re.search(f'(?<!`){quote}', escaped) is None


@pytest.mark.parametrize('quote', list(PS_SINGLE) + ["'"])
def test_powershell_single_quoted_escape_doubles_every_single_quote(quote):
    escaped = _powershell_escape_squoted(f'a{quote}b')
    assert escaped == f'a{quote}{quote}b'


def test_powershell_plan_name_is_escaped_in_banner_and_menu():
    name = f'P”; Write-Output pwned; “$x'
    script = generate_script({'name': name, 'description': ''}, [ITEM], 'powershell')
    for line in script.splitlines():
        if 'Plan:' in line and 'Write-Host' in line:
            assert '`”' in line and '`$x' in line, line


def test_powershell_input_defaults_use_powershell_quoting():
    item = {**ITEM, 'executor_command': 'echo #{p}',
            'input_arguments': '{"p": {"description": "d", "type": "string", "default": "it’s; Write-Output pwned"}}'}
    script = generate_script({'name': 'P', 'description': ''}, [item], 'powershell')
    assert "it’’s; Write-Output pwned" in script
    assert '\'"\'"\'' not in script  # the bash single-quote escape has no meaning in PowerShell

"""Safety prompts in generated test scripts (utils/script_generator).

Generated scripts run attacker techniques, so before anything executes the
operator must confirm the host is in scope; unattended runs need an explicit
"RUN ALL"; elevation and cleanup are surfaced rather than silently ignored.
"""

import os
import re
import shutil
import subprocess
import tempfile

import pytest

from utils.script_generator import generate_readme, generate_script

PLAN = {'name': 'Safety "plan"', 'description': ''}
ITEMS = [
    {   # needs root, has a defaulted input and a cleanup step; name needs escaping
        'id': 1, 'enabled': 1, 'technique_id': 'T1003', 'atomic_test_name': 'Dump "quoted" $creds',
        'executor_command': "echo 'hello' > #{outfile}", 'executor_cleanup': 'rm -f #{outfile}',
        'supported_platforms': '["linux", "windows"]',
        'input_arguments': '{"outfile": {"description": "Output", "type": "path", "default": "/tmp/x.txt"}}',
        'elevation_required': 1,
    },
    {   # required input with no default: can't run unattended
        'id': 2, 'enabled': 1, 'technique_id': 'T1059', 'atomic_test_name': 'Needs target',
        'executor_command': 'echo #{target}', 'executor_cleanup': None,
        'supported_platforms': '["linux", "windows"]',
        'input_arguments': '{"target": {"description": "Target", "type": "string"}}',
        'elevation_required': 0,
    },
    {   # custom test with cleanup, no technique
        'id': 3, 'enabled': 1, 'technique_id': None, 'custom_name': 'Custom whoami',
        'custom_command': 'whoami', 'executor_cleanup': 'echo cleaned',
        'supported_platforms': None, 'input_arguments': None, 'elevation_required': 0,
    },
]


@pytest.fixture(scope='module')
def bash_script():
    return generate_script(PLAN, ITEMS, 'bash')


@pytest.fixture(scope='module')
def ps_script():
    return generate_script(PLAN, ITEMS, 'powershell')


def _function_body(script, start, end_marker):
    a = script.index(start)
    return script[a:script.index(end_marker, a)]


# --------------------------------------------------------------------- bash

@pytest.mark.skipif(not shutil.which('bash'), reason='bash not available')
def test_bash_script_is_valid_syntax(bash_script):
    with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as fh:
        fh.write(bash_script)
    try:
        result = subprocess.run(['bash', '-n', fh.name], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    finally:
        os.unlink(fh.name)


def test_bash_has_no_template_leftovers(bash_script):
    assert '{{' not in bash_script
    assert 'len(compatible_items)' not in bash_script
    assert not re.search(r'__(PLAN|TOTAL|ELEVATED|CLEANUP)__', bash_script)


def test_bash_confirms_authorization_before_anything_runs(bash_script):
    tail = bash_script.rstrip().splitlines()[-2:]
    assert tail == ['confirm_authorization', 'select_execution_mode']
    assert 'Tests:       3 (1 need root, 2 have a cleanup step)' in bash_script
    assert 'Plan:        Safety \\"plan\\"' in bash_script
    assert 'PTVAULT_AUTHORIZED_HOST' in bash_script


def test_bash_automatic_mode_requires_run_all(bash_script):
    assert re.search(r'1\)\n\s+if confirm_automatic; then\n\s+run_automatic', bash_script)
    assert 'read -p "Type RUN ALL to continue' in bash_script


def test_bash_automatic_mode_uses_defaults_skips_and_cleans_up(bash_script):
    auto = _function_body(bash_script, 'run_automatic() {', '\n}\n')
    # Defaults substituted, original command kept intact (no quote mangling)
    assert "outfile='/tmp/x.txt'" in auto
    assert "echo 'hello' > ${outfile}" in auto
    assert '#{outfile}' not in auto
    # Root-only test is skipped when not elevated
    assert 'Test 1 skipped (requires root): T1003 [item=1]' in auto
    # Required input without a default is skipped, never run with a placeholder
    assert 'Test 2 skipped (needs input with no default: target): T1059 [item=2]' in auto
    assert 'echo ${target}' not in auto
    # Cleanup runs and is tracked
    assert 'rm -f ${outfile}' in auto
    assert 'CLEANUP["test_3"]="DONE"' in auto


def test_bash_per_test_cleanup_defaults_to_yes_and_is_tracked(bash_script):
    test1 = _function_body(bash_script, 'test_1() {', '\n}\n')
    assert 'Run cleanup command? [Y/n]' in test1
    assert 'CLEANUP["test_1"]="SKIPPED"' in test1
    assert 'Cleanup skipped for test 1: T1003 - artifacts may remain [item=1]' in test1
    assert 'This test requires root' in test1
    assert 'This test requires root' not in _function_body(bash_script, 'test_2() {', '\n}\n')


def test_bash_summary_lists_cleanups_that_did_not_run(bash_script):
    summary = _function_body(bash_script, 'show_results() {', '\n}\n')
    assert 'CLEANUP["test_1"]' in summary and 'CLEANUP["test_3"]' in summary
    assert 'CLEANUP["test_2"]' not in summary          # no cleanup step
    assert 'artifacts may remain on this system' in summary


def test_bash_test_names_are_escaped(bash_script):
    assert 'Dump \\"quoted\\" \\$creds' in bash_script
    assert 'Dump "quoted" $creds' not in bash_script


# ------------------------------------------------- bash runtime (bash 3.2+)

def _run_bash(script, snippet, stdin='', env=None):
    """Source the generated functions (without running main) and run a snippet."""
    body = script.rsplit('confirm_authorization\nselect_execution_mode', 1)[0]
    with tempfile.NamedTemporaryFile('w', suffix='.sh', delete=False) as fh:
        fh.write(body)
    try:
        full_env = {**os.environ, 'TERM': 'dumb'}
        full_env.pop('PTVAULT_AUTHORIZED_HOST', None)
        full_env.update(env or {})
        return subprocess.run(['bash', '-c', f'source "{fh.name}" 2>/dev/null; {snippet}'],
                              input=stdin, capture_output=True, text=True, env=full_env, timeout=20)
    finally:
        os.unlink(fh.name)


def _hostname():
    return subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()


needs_bash = pytest.mark.skipif(not shutil.which('bash') or not shutil.which('hostname'),
                                reason='bash/hostname not available')


@needs_bash
def test_runtime_wrong_hostname_stops_the_script(bash_script):
    result = _run_bash(bash_script, 'confirm_authorization; echo REACHED', stdin='not-this-host\n')
    assert result.returncode == 1
    assert 'Nothing was run' in result.stdout
    assert 'REACHED' not in result.stdout


@needs_bash
def test_runtime_correct_hostname_continues_and_is_logged(bash_script):
    host = _hostname()
    result = _run_bash(bash_script, 'confirm_authorization; echo REACHED', stdin=f'{host}\n')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'REACHED' in result.stdout
    assert 'Authorization confirmed by' in result.stdout and host in result.stdout


@needs_bash
def test_runtime_env_var_authorizes_unattended_runs(bash_script):
    host = _hostname()
    ok = _run_bash(bash_script, 'confirm_authorization; echo REACHED', env={'PTVAULT_AUTHORIZED_HOST': host})
    assert ok.returncode == 0 and 'REACHED' in ok.stdout
    assert 'via PTVAULT_AUTHORIZED_HOST' in ok.stdout
    bad = _run_bash(bash_script, 'confirm_authorization; echo REACHED',
                    env={'PTVAULT_AUTHORIZED_HOST': 'other-box'})
    assert bad.returncode == 1 and 'REACHED' not in bad.stdout
    assert 'does not match this host' in bad.stdout


@needs_bash
@pytest.mark.parametrize('answer,expected', [('RUN ALL', 0), ('run all', 1), ('', 1), ('y', 1)])
def test_runtime_automatic_mode_needs_exact_run_all(bash_script, answer, expected):
    result = _run_bash(bash_script, 'confirm_automatic', stdin=f'{answer}\n')
    assert result.returncode == expected, result.stdout


# --------------------------------------------------------------- PowerShell

def test_powershell_has_no_template_leftovers(ps_script):
    assert '{len(' not in ps_script
    assert not re.search(r'__(PLAN|TOTAL|ELEVATED|CLEANUP)__', ps_script)


def test_powershell_confirms_authorization_before_anything_runs(ps_script):
    tail = ps_script.rstrip().splitlines()[-2:]
    assert tail == ['Confirm-Authorization', 'Select-ExecutionMode']
    assert 'Tests:       3 (1 need Administrator, 2 have a cleanup step)' in ps_script
    assert '$answer -ine $hostName' in ps_script


def test_powershell_automatic_mode_requires_run_all(ps_script):
    assert '"^1$" { if (Confirm-Automatic) { Run-Automatic } else { Select-ExecutionMode } }' in ps_script
    assert '$answer -cne "RUN ALL"' in ps_script


def test_powershell_automatic_mode_uses_defaults_skips_and_cleans_up(ps_script):
    auto = _function_body(ps_script, 'function Run-Automatic {', '\n}\n')
    assert "$autoVars = @{ 'outfile' = '/tmp/x.txt' }" in auto
    assert 'Test 1 skipped (requires Administrator): T1003 [item=1]' in auto
    assert 'Test 2 skipped (needs input with no default: target): T1059 [item=2]' in auto
    assert '$global:Cleanup["Test-3"] = "DONE"' in auto


def test_powershell_per_test_cleanup_defaults_to_yes(ps_script):
    test1 = _function_body(ps_script, 'function Test-1 {', '\n}\n')
    assert 'Run cleanup command? [Y/n]' in test1
    assert '$doCleanup -notmatch "^[Nn]"' in test1
    assert '$global:Cleanup["Test-1"] = "SKIPPED"' in test1
    assert 'This test requires Administrator' in test1


def test_powershell_summary_lists_cleanups_that_did_not_run(ps_script):
    summary = _function_body(ps_script, 'function Show-Results {', '\n}\n')
    assert '$global:Cleanup["Test-1"]' in summary and '$global:Cleanup["Test-3"]' in summary
    assert 'artifacts may remain on this system' in summary


def test_powershell_test_names_are_escaped(ps_script):
    assert 'Dump `"quoted`" `$creds' in ps_script


def test_readme_documents_the_safety_checks():
    readme = generate_readme(PLAN, ITEMS, 'bash')
    assert '## Safety Checks' in readme
    assert 'PTVAULT_AUTHORIZED_HOST' in readme
    assert 'RUN ALL' in readme

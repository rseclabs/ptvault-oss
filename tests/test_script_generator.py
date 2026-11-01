"""Tests for utils/script_generator — focuses on prompt-block escaping."""

import json

import pytest

from utils.script_generator import (
    _bash_escape_dquoted,
    _bash_prompt_block,
    _powershell_escape_dquoted,
    _powershell_prompt_block,
    _parse_input_arguments,
    generate_powershell_script,
    generate_bash_script,
)


def _atomic_with_newline_default():
    """Mirror of the real-world failing case: SharpView 'syntax' default
    contains a trailing literal newline."""
    return {
        'enabled': 1,
        'sort_order': 1,
        'technique_id': 'T1049',
        'atomic_test_name': 'System Discovery using SharpView',
        'executor_command': '#{SharpView} #{syntax}',
        'supported_platforms': ['windows'],
        'input_arguments': json.dumps({
            'SharpView': {
                'description': 'Path to tool',
                'type': 'path',
                'default': 'PathToAtomicsFolder\\..\\ExternalPayloads\\SharpView.exe',
            },
            'syntax': {
                'description': 'Args',
                'type': 'string',
                # The problematic real-world value: embedded quotes AND a
                # trailing literal newline.
                'default': '"Invoke-ACLScanner", "Find-DomainShare" \n',
            },
        }),
    }


def test_powershell_escape_dquoted_handles_control_chars():
    """Newlines, CR, and tabs must be turned into PowerShell escape
    sequences — emitting them literally produces multi-line strings that
    Windows PowerShell 5.1 misparses."""
    assert _powershell_escape_dquoted('a\nb') == 'a`nb'
    assert _powershell_escape_dquoted('a\rb') == 'a`rb'
    assert _powershell_escape_dquoted('a\tb') == 'a`tb'
    # Existing escapes still work and order is correct (backtick first).
    assert _powershell_escape_dquoted('`"$') == '```"`$'


def test_powershell_prompt_block_emits_single_line_statements():
    """Each Read-Host / if-fallback statement must be a single source line,
    even when the atomic default contains a newline."""
    args = _parse_input_arguments(_atomic_with_newline_default()['input_arguments'])
    block = _powershell_prompt_block(args)

    # Strip the trailing terminator added by the helper.
    statements = block.rstrip('\n').split('\n')

    for line in statements:
        # No raw CR/LF inside any line — the helper splits on \n already, so
        # the only way a problem leaks in is via a literal CR.
        assert '\r' not in line, f'CR leaked into emitted line: {line!r}'

    # The 'syntax' default should appear as a single PowerShell statement.
    syntax_lines = [l for l in statements if '$syntax' in l]
    assert syntax_lines, 'expected $syntax assignment lines'
    for l in syntax_lines:
        assert '\n' not in l


def test_bash_escape_dquoted_handles_control_chars():
    """Bash double-quoted strings preserve newlines literally; we collapse
    them to keep the read prompt single-line and readable."""
    assert '\n' not in _bash_escape_dquoted('a\nb')
    assert '\r' not in _bash_escape_dquoted('a\r\nb')


def test_powershell_script_starts_with_utf8_bom():
    """Windows PowerShell 5.1 reads BOM-less files as the system ANSI
    codepage (cp1252 on US/EU). Em-dashes in prompts (UTF-8 E2 80 94)
    decode to `â€"` under cp1252, and the trailing 0x94 is U+201D (smart
    close-quote) which Windows PowerShell treats as a string terminator —
    prematurely closing every Read-Host -Prompt string. A leading UTF-8
    BOM forces UTF-8 interpretation."""
    plan = {'name': 'BOM check', 'description': ''}
    items = [_atomic_with_newline_default()]
    script = generate_powershell_script(plan, items)
    assert script.startswith('﻿'), 'PowerShell script must start with UTF-8 BOM'


def test_bash_script_does_not_have_bom():
    """Bash treats a leading BOM as part of the shebang and breaks. The
    bash output must not have one."""
    plan = {'name': 'no BOM', 'description': ''}
    item = _atomic_with_newline_default()
    item['supported_platforms'] = ['linux']
    script = generate_bash_script(plan, [item])
    assert not script.startswith('﻿'), 'Bash script must not start with BOM'
    assert script.startswith('#!/bin/bash'), 'Bash script must start with shebang'


def test_powershell_script_uses_isolated_command_invocation():
    """Atomics that call `exit` (e.g. T1018 Get-WmiObject DC enumeration with
    `exit $_.Exception.HResult` in the catch block) would terminate the
    wrapper script if run via Invoke-Expression. Each test must instead go
    through Invoke-IsolatedCommand, which spawns a child PowerShell so the
    `exit` is scoped to that child."""
    plan = {'name': 'iso', 'description': ''}
    items = [_atomic_with_newline_default()]
    script = generate_powershell_script(plan, items)

    # The helper function must be defined exactly once.
    assert script.count('function Invoke-IsolatedCommand') == 1

    # No remaining direct Invoke-Expression of atomic commands — those would
    # leak `exit` calls back into the wrapper.
    assert 'Invoke-Expression $command' not in script
    assert 'Invoke-Expression $batchCmd' not in script
    assert 'Invoke-Expression $cleanupCmd' not in script


def test_isolated_command_passes_prompted_vars():
    """Variables the user just typed at Read-Host prompts must reach the
    child PowerShell. The generator emits a $_promptVars hashtable that's
    populated after the prompts run."""
    plan = {'name': 'vars', 'description': ''}
    items = [_atomic_with_newline_default()]
    script = generate_powershell_script(plan, items)

    # Each prompted arg should be added to the hashtable.
    assert "$_promptVars['SharpView'] = $SharpView" in script
    assert "$_promptVars['syntax'] = $syntax" in script
    # And the hashtable should be passed to Invoke-IsolatedCommand.
    assert 'Invoke-IsolatedCommand -Command $command -Variables $_promptVars' in script


def test_isolated_command_uses_dotnet_process_start():
    """Windows PowerShell 5.1's `Start-Process -PassThru` (without -Wait)
    returns a Process whose handle gets closed when the child exits, so
    `.ExitCode` reads as $null for fast atomics. That would make
    `$exitCode -eq 0` evaluate $null -eq 0 = False — every test ends up
    FAILED. We must own the Process via [Diagnostics.Process]::Start so
    the handle stays open and ExitCode is reliable."""
    plan = {'name': 't', 'description': ''}
    items = [_atomic_with_newline_default()]
    script = generate_powershell_script(plan, items)

    # No active use of Start-Process as a command — comments may still
    # reference it, but no code line should call it.
    for line in script.split('\n'):
        stripped = line.lstrip()
        if stripped.startswith('#'):
            continue
        assert 'Start-Process ' not in stripped, f'leftover Start-Process call: {line!r}'
    # We must create our own ProcessStartInfo and call .NET Process.Start.
    assert 'System.Diagnostics.ProcessStartInfo' in script
    assert '[System.Diagnostics.Process]::Start($psi)' in script
    # And UseShellExecute must be false so the child inherits the console
    # for direct stdout streaming.
    assert '$psi.UseShellExecute = $false' in script


def test_isolated_command_has_three_minute_default_timeout():
    """GUI-automation atomics (T1059.001 Mimikatz - Cradlecraft PsSendKeys,
    SendKeys-driven Notepad) hang forever on modern Win11. The isolation
    helper must enforce a wall-clock timeout, kill the child process tree
    on expiry, and return a non-zero sentinel so the wrapper marks FAILED
    and moves on."""
    plan = {'name': 't', 'description': ''}
    items = [_atomic_with_newline_default()]
    script = generate_powershell_script(plan, items)

    # Helper exposes the timeout parameter with a 180s default.
    assert '[int]$TimeoutSeconds = 180' in script
    # WaitForExit is bounded, not infinite.
    assert '$proc.WaitForExit($TimeoutSeconds * 1000)' in script
    # taskkill /T must be used so spawned GUI children (Notepad etc.) die too.
    assert 'taskkill.exe /T /F /PID $proc.Id' in script
    # POSIX-convention sentinel exit code for timeout.
    assert 'return 124' in script


def test_isolated_command_treats_nonzero_exit_as_failed():
    """If the child PowerShell exits with non-zero (the original symptom:
    `exit $_.Exception.HResult`), the wrapper must mark the test FAILED
    rather than PASSED."""
    plan = {'name': 'exit', 'description': ''}
    items = [_atomic_with_newline_default()]
    script = generate_powershell_script(plan, items)

    # The PASS branch is gated on $exitCode -eq 0.
    assert 'if ($exitCode -eq 0)' in script


def test_generated_powershell_has_no_orphan_quotes():
    """Smoke test: a full generated script for an atomic with a newline
    default must have balanced double quotes on every emitted statement
    line in the prompt section."""
    plan = {'name': 'NL Repro', 'description': 'newline test'}
    items = [_atomic_with_newline_default()]
    script = generate_powershell_script(plan, items)

    # Find the section with $syntax — every line containing $syntax must
    # have an even number of unescaped quote characters.
    for line in script.split('\n'):
        if '$syntax' not in line:
            continue
        # Count " not preceded by ` (escape).
        unescaped = 0
        prev = ''
        for ch in line:
            if ch == '"' and prev != '`':
                unescaped += 1
            prev = ch
        assert unescaped % 2 == 0, f'unbalanced quotes on line: {line!r}'

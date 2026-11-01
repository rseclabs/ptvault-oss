"""Tests for utils/session_log_parser (session.log import)."""

import re

from utils.script_generator import generate_script
from utils.session_log_parser import decode_log, parse_session_log

ESC = '\x1b'


def _c(code, text):
    """Wrap text in an ANSI colour, like the generated scripts' echo -e."""
    return f"{ESC}[{code}m{text}{ESC}[0m"


TAGGED_LOG = "\n".join([
    "Script started on Sat Oct 31 14:00:00 2026",
    f"{_c('0;35', '[2026-10-31 14:02:11]')} {_c('0;36', '[INFO]')} Preparing test: T1003.001 - Dump LSASS",
    "Execute this test? [y/N/s(kip)] y",
    f"{_c('0;35', '[2026-10-31 14:02:15]')} {_c('0;32', '[START]')} Executing test 1: T1003.001 - Dump LSASS [item=42]",
    "",
    _c('0;36', '--- Command Output ----------------------------------------------'),
    "procdump written to C:\\Temp\\lsass.dmp",
    "second line",
    _c('0;36', '-----------------------------------------------------------------'),
    "",
    f"{_c('0;35', '[2026-10-31 14:02:19]')} {_c('0;32', '[PASS]')} Test 1 completed successfully (exit code: 0, duration: 4s) [item=42]",
    f"{_c('0;35', '[2026-10-31 14:02:19]')} {_c('0;34', '[END]')} Finished test 1: T1003.001 [item=42]",
    f"{_c('0;35', '[2026-10-31 14:03:00]')} {_c('0;36', '[INFO]')} Preparing test: T1059.001 - PowerShell download cradle",
    f"{_c('0;35', '[2026-10-31 14:03:01]')} {_c('1;33', '[SKIP]')} Test 2 skipped by user: T1059.001 [item=43]",
    f"{_c('0;35', '[2026-10-31 14:04:00]')} {_c('0;36', '[INFO]')} Preparing test: Custom - whoami check",
    f"{_c('0;35', '[2026-10-31 14:04:02]')} {_c('0;32', '[START]')} Executing test 3: Custom - whoami check [item=44]",
    _c('0;36', '--- Command Output ----------------------------------------------'),
    "access denied",
    _c('0;36', '-----------------------------------------------------------------'),
    f"{_c('0;35', '[2026-10-31 14:04:03]')} {_c('0;31', '[FAIL]')} Test 3 failed (exit code: 5, duration: 1s) [item=44]",
])


def test_parses_tagged_bash_log_with_ansi():
    results = parse_session_log(TAGGED_LOG)
    assert [r['test_number'] for r in results] == [1, 2, 3]

    first, skipped, failed = results
    assert first['item_id'] == 42
    assert first['technique_id'] == 'T1003.001'
    assert first['test_name'] == 'Dump LSASS'
    assert first['status'] == 'completed'
    assert first['exit_code'] == 0
    assert first['duration_seconds'] == 4.0
    assert first['started_at'] == '2026-10-31 14:02:15'
    assert first['completed_at'] == '2026-10-31 14:02:19'
    assert first['output'] == 'procdump written to C:\\Temp\\lsass.dmp\nsecond line'

    assert skipped['status'] == 'skipped'
    assert skipped['item_id'] == 43
    assert skipped['technique_id'] == 'T1059.001'
    assert skipped['test_name'] == 'PowerShell download cradle'

    assert failed['status'] == 'failed'
    assert failed['exit_code'] == 5
    assert failed['technique_id'] is None        # "Custom" means no technique
    assert failed['output'] == 'access denied'


def test_untagged_legacy_log_still_parses():
    legacy = re.sub(r' \[item=\d+\]', '', TAGGED_LOG)
    results = parse_session_log(legacy)
    assert [r['item_id'] for r in results] == [None, None, None]
    assert results[0]['test_name'] == 'Dump LSASS'
    assert results[1]['status'] == 'skipped'


def test_crlf_and_carriage_return_progress_lines():
    log = TAGGED_LOG.replace('\n', '\r\n').replace('second line', 'progress 10%\rprogress 100%')
    results = parse_session_log(log)
    assert results[0]['output'] == 'procdump written to C:\\Temp\\lsass.dmp\nprogress 100%'


def test_utf16_powershell_transcript():
    transcript = "\r\n".join([
        "**********************",
        "Windows PowerShell transcript start",
        "Start time: 20261031140000",
        "**********************",
        "[2026-10-31 14:02:11] [INFO] Preparing test: T1003.001 - Dump LSASS",
        "[2026-10-31 14:02:15] [START] Executing test 1: T1003.001 - Dump LSASS [item=42]",
        "--- Command Output ----------------------------------------------",
        "ok",
        "-----------------------------------------------------------------",
        "[2026-10-31 14:02:19] [PASS] Test 1 completed successfully (duration: 4.2s) [item=42]",
        "[2026-10-31 14:03:19] [FAIL] Test 2 failed: Access is denied. (duration: 0.3s) [item=43]",
    ])
    for raw in (transcript.encode('utf-16'), transcript.encode('utf-16-le')):
        results = parse_session_log(decode_log(raw))
        assert results[0]['status'] == 'completed'
        assert results[0]['exit_code'] == 0
        assert results[0]['duration_seconds'] == 4.2
        assert results[0]['output'] == 'ok'
        # FAIL without a START line still produces a result
        assert results[1]['status'] == 'failed'
        assert results[1]['item_id'] == 43


def test_rerun_last_result_wins_and_unfinished_test_is_in_progress():
    log = "\n".join([
        "[2026-10-31 10:00:00] [START] Executing test 1: T1 - A [item=1]",
        "[2026-10-31 10:00:01] [FAIL] Test 1 failed (exit code: 1, duration: 1s) [item=1]",
        "[2026-10-31 10:05:00] [START] Executing test 1: T1 - A [item=1]",
        "[2026-10-31 10:05:02] [PASS] Test 1 completed successfully (exit code: 0, duration: 2s) [item=1]",
        "[2026-10-31 10:06:00] [START] Executing test 2: T2 - B [item=2]",
        "--- Command Output ----------------------------------------------",
        "partial output before the session was cut",
    ])
    results = parse_session_log(log)
    assert results[0]['status'] == 'completed'
    assert results[0]['started_at'] == '2026-10-31 10:05:00'
    assert results[1]['status'] == 'in_progress'
    assert results[1]['output'] == 'partial output before the session was cut'


def test_batch_lines_and_noise_are_ignored():
    log = "\n".join([
        "[2026-10-31 10:00:00] [START] Beginning batch execution of all 2 tests",
        "random text [START] not an event",
        "[2026-10-31 10:09:00] [END] Batch execution completed (total duration: 9s)",
    ])
    assert parse_session_log(log) == []


def test_output_is_truncated():
    big = "x" * (70 * 1024)
    log = "\n".join([
        "[2026-10-31 10:00:00] [START] Executing test 1: T1 - A [item=1]",
        "--- Command Output ----------------------------------------------",
        big,
        "-----------------------------------------------------------------",
        "[2026-10-31 10:00:01] [PASS] Test 1 completed successfully (exit code: 0, duration: 1s) [item=1]",
    ])
    output = parse_session_log(log)[0]['output']
    assert output.endswith('[... output truncated by PTVault import ...]')
    assert len(output) < 70 * 1024


def _item(item_id, name, technique='T1003', command='whoami'):
    return {
        'id': item_id, 'enabled': 1, 'atomic_test_name': name, 'technique_id': technique,
        'executor_command': command, 'supported_platforms': '["linux", "windows"]',
        'input_arguments': None, 'executor_cleanup': None,
    }


def _expand(message, idx):
    """Fill in the shell variables a real run would expand."""
    return (message.replace('$exit_code', '0').replace('${duration}', '3')
            .replace(f'$exit_code_{idx}', '0').replace(f'${{duration_{idx}}}', '3')
            .replace('$([math]::Round($duration,1))', '3'))


def test_generated_scripts_emit_lines_the_parser_maps_to_items():
    """Contract test: the generators' log messages parse back to item ids."""
    plan = {'name': 'Contract', 'description': ''}
    items = [_item(42, 'Dump LSASS'), _item(43, 'Second test', 'T1059')]

    for platform, pattern in (
        ('bash', r'log_event "(START|PASS|SKIP)" "([^"]*\[item=\d+\])"'),
        ('powershell', r'-Level "(START|PASS|SKIP)" -Message "([^"]*\[item=\d+\])"'),
    ):
        script = generate_script(plan, items, platform)
        lines = []
        for level, message in re.findall(pattern, script):
            idx = re.search(r'[Tt]est (\d+)', message).group(1)
            lines.append(f"[2026-10-31 10:00:0{idx}] [{level}] {_expand(message, idx)}")
        results = parse_session_log("\n".join(lines))
        by_number = {r['test_number']: r for r in results}
        assert by_number[1]['item_id'] == 42, platform
        assert by_number[2]['item_id'] == 43, platform

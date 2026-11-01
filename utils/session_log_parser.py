"""Parse session logs produced by PTVault-generated test scripts.

The Bash and PowerShell scripts from utils/script_generator.py print
timestamped event lines:

    [2026-10-31 14:02:11] [INFO] Preparing test: T1003.001 - Dump LSASS
    [2026-10-31 14:02:15] [START] Executing test 3: T1003.001 - Dump LSASS [item=42]
    --- Command Output ----------------------------------------------
    ...command output...
    -----------------------------------------------------------------
    [2026-10-31 14:02:19] [PASS] Test 3 completed successfully (exit code: 0, duration: 4s) [item=42]
    [2026-10-31 14:02:19] [END] Finished test 3: T1003.001 [item=42]
    [2026-10-31 14:03:01] [SKIP] Test 4 skipped by user: T1059.001 [item=43]

Logs come from `tee`, `script`, `Tee-Object` or `Start-Transcript`, so the
parser tolerates ANSI colour codes, carriage returns, UTF-16 (Windows
PowerShell 5 Tee-Object), and transcript headers. Scripts generated before
the `[item=N]` tag existed are still parsed; results then carry only the
technique and test name for matching.
"""

import re

MAX_LOG_BYTES = 10 * 1024 * 1024        # refuse anything bigger
MAX_OUTPUT_CHARS = 64 * 1024            # per test, keeps rows reasonable

_ANSI = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]')
_EVENT = re.compile(
    r'^\s*\[(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\]\s*'
    r'\[(START|END|PASS|FAIL|SKIP|INFO|EXEC)\]\s*(.*?)\s*$'
)
_ITEM_TAG = re.compile(r'\s*\[item=(\d+)\]\s*$')
_TEST_NUM = re.compile(r'\b[Tt]est (\d+)\b')
_EXECUTING = re.compile(r'^Executing test (\d+):\s*(.*?)\s+-\s+(.*)$')
_PREPARING = re.compile(r'^Preparing test:\s*(.*?)\s+-\s+(.*)$')
_EXIT_CODE = re.compile(r'exit code:\s*(-?\d+)')
_DURATION = re.compile(r'duration:\s*([\d.]+)s')
_OUTPUT_START = re.compile(r'^-{2,}\s*Command Output\s*-*\s*$')
_RULE = re.compile(r'^-{10,}\s*$')

_NO_TECHNIQUE = {'', 'custom', 'none', 'null'}


def decode_log(raw: bytes) -> str:
    """Decode log bytes, handling UTF-16 (BOM or NUL-interleaved) and UTF-8."""
    if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
        return raw.decode('utf-16', errors='replace')
    # UTF-16LE without BOM: every other byte of ASCII text is NUL
    sample = raw[:400]
    if sample and sample[1::2].count(0) > len(sample) // 4:
        return raw.decode('utf-16-le', errors='replace')
    return raw.decode('utf-8-sig', errors='replace')


def _clean(line: str) -> str:
    line = _ANSI.sub('', line)
    # `script` and Windows consoles leave \r; keep the text after the last one
    if '\r' in line:
        parts = [p for p in line.split('\r') if p]
        line = parts[-1] if parts else ''
    return line.rstrip()


def _norm_technique(value):
    value = (value or '').strip()
    return None if value.lower() in _NO_TECHNIQUE else value


def _split_tag(message):
    """Return (message without [item=N], item_id or None)."""
    m = _ITEM_TAG.search(message)
    if not m:
        return message, None
    return message[:m.start()].rstrip(), int(m.group(1))


def parse_session_log(text: str):
    """
    Parse a session log into one result per test number.

    Returns a list of dicts ordered by test number:
        test_number, item_id, technique_id, test_name,
        status ('completed' | 'failed' | 'skipped' | 'in_progress'),
        exit_code, duration_seconds, started_at, completed_at, output
    If a test ran more than once (e.g. re-run from the menu), the last run wins.
    """
    results = {}
    prepared = None          # (technique, name) from the latest "Preparing test"
    current = None           # result dict for the test whose output we're reading
    capturing = False
    output_lines = []

    def finish_capture():
        nonlocal capturing, output_lines
        if current is not None and capturing:
            text_out = '\n'.join(output_lines).strip('\n')
            if len(text_out) > MAX_OUTPUT_CHARS:
                text_out = text_out[:MAX_OUTPUT_CHARS] + '\n[... output truncated by PTVault import ...]'
            current['output'] = text_out
        capturing = False
        output_lines = []

    # split('\n') rather than splitlines(): a bare \r is a terminal redraw
    # (progress bars) and _clean() keeps only the final text on that line
    for raw_line in text.split('\n'):
        line = _clean(raw_line)

        event = _EVENT.match(line)
        if not event:
            if current is not None and not capturing and _OUTPUT_START.match(line.strip()):
                capturing = True
                output_lines = []
            elif capturing:
                if _RULE.match(line.strip()):
                    finish_capture()
                else:
                    output_lines.append(line)
            continue

        ts, level, message = event.groups()
        ts = ts.replace('T', ' ')
        message, item_id = _split_tag(message)

        if level == 'INFO':
            m = _PREPARING.match(message)
            if m:
                prepared = (_norm_technique(m.group(1)), m.group(2).strip())
            continue

        if level == 'START':
            m = _EXECUTING.match(message)
            if not m:
                continue   # batch-level START ("Beginning batch execution ...")
            finish_capture()
            number = int(m.group(1))
            current = {
                'test_number': number,
                'item_id': item_id,
                'technique_id': _norm_technique(m.group(2)),
                'test_name': m.group(3).strip(),
                'status': 'in_progress',
                'exit_code': None,
                'duration_seconds': None,
                'started_at': ts,
                'completed_at': None,
                'output': '',
            }
            results[number] = current
            continue

        number_match = _TEST_NUM.search(message)
        if not number_match:
            continue   # batch-level END etc.
        number = int(number_match.group(1))

        if level in ('PASS', 'FAIL'):
            finish_capture()
            result = results.get(number)
            if result is None:
                # Result without a START line (log started mid-test)
                technique, name = prepared or (None, '')
                result = results[number] = {
                    'test_number': number, 'item_id': item_id, 'technique_id': technique,
                    'test_name': name, 'started_at': None, 'output': '',
                }
            result['status'] = 'completed' if level == 'PASS' else 'failed'
            result['item_id'] = result.get('item_id') or item_id
            code = _EXIT_CODE.search(message)
            result['exit_code'] = int(code.group(1)) if code else (0 if level == 'PASS' else None)
            dur = _DURATION.search(message)
            result['duration_seconds'] = float(dur.group(1)) if dur else None
            result['completed_at'] = ts
        elif level == 'SKIP':
            finish_capture()
            technique, name = prepared or (None, '')
            skip_technique = message.rsplit(':', 1)[-1].strip() if ':' in message else None
            results[number] = {
                'test_number': number,
                'item_id': item_id,
                'technique_id': _norm_technique(skip_technique) or technique,
                'test_name': name,
                'status': 'skipped',
                'exit_code': None,
                'duration_seconds': None,
                'started_at': None,
                'completed_at': ts,
                'output': '',
            }
            current = None
        elif level == 'END':
            finish_capture()
            if current is not None and current.get('test_number') == number:
                current = None

    finish_capture()
    return [results[n] for n in sorted(results)]

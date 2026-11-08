"""M-7: session-log parsing is linear in the line length.

`(.*?)\\s*$` and `(.*?)\\s+-\\s+` backtrack quadratically over a long run of
whitespace, so one crafted line in an imported (or previewed) log could tie
up a worker for hours at the 10 MB limit. Lines are also capped in length.
"""

import time

import pytest

from utils.session_log_parser import MAX_LINE_CHARS, parse_session_log

TS = '[2026-01-01 00:00:00]'
W = " " * 200_000       # minutes per line with the old quadratic patterns (1.5 s at 20 000); milliseconds now


@pytest.mark.parametrize('line', [
    f'{TS} [INFO] a{W}b',
    f'{TS} [INFO] a{W}b [item=1]',
    f'{TS} [EXEC] Executing test 1: a{W}b',
    f'{TS} [INFO] Preparing test: a{W}b',
    f'{TS} [START] {W}x',
], ids=['event', 'item-tag', 'executing', 'preparing', 'leading-space'])
def test_whitespace_runs_parse_quickly(line):
    start = time.perf_counter()
    parse_session_log(line + '\n')
    assert time.perf_counter() - start < 1.0


def test_overlong_lines_are_capped():
    text = f'{TS} [EXEC] Executing test 1: T1059 - {"x" * (MAX_LINE_CHARS * 3)}\n'
    result = parse_session_log(text)
    names = repr(result)
    assert 'x' * (MAX_LINE_CHARS + 1) not in names


@pytest.mark.parametrize('message, expected', [
    ('Executing test 3: T1059.001 - PowerShell download', ('3', 'T1059.001', 'PowerShell download')),
    ('Executing test 3:   T1059   -\tName - with dash', ('3', 'T1059', 'Name - with dash')),
])
def test_executing_lines_still_split_on_the_first_dash(message, expected):
    from utils.session_log_parser import _split_executing
    assert _split_executing(message) == expected

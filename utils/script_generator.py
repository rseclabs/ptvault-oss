"""
Script Generator for PTVault Test Plans.
Generates executable Bash and PowerShell scripts from test plans.
"""

import json
import re
from datetime import datetime


# ---------------------------------------------------------------------------
# Atomic Red Team input_arguments handling
#
# Atomic tests use #{argument_name} placeholder syntax in their executor
# commands. The atomic's input_arguments dict declares each argument's
# description, type, and optional default value. The generated script must:
#   1. Prompt the user for each argument at runtime (showing description +
#      default), and
#   2. Substitute #{argname} placeholders with the prompted shell variable.
# ---------------------------------------------------------------------------


def _parse_input_arguments(raw):
    """Coerce an input_arguments value (dict, JSON string, or None) into a
    list of {name, description, type, default} entries. Malformed input
    becomes an empty list — best-effort, never raises."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(raw, dict):
        return []
    args = []
    for name, meta in raw.items():
        if not isinstance(name, str) or not name:
            continue
        meta = meta if isinstance(meta, dict) else {}
        default = meta.get('default')
        args.append({
            'name': name,
            'description': str(meta.get('description', '') or ''),
            'type': str(meta.get('type', '') or ''),
            'default': '' if default is None else str(default),
        })
    return args


def _shell_safe_name(name):
    """Sanitise an arbitrary string into a valid shell variable name. Both
    bash and PowerShell accept [A-Za-z_][A-Za-z0-9_]*."""
    out = re.sub(r'[^A-Za-z0-9_]', '_', name)
    if not out or out[0].isdigit():
        out = '_' + out
    return out


def _substitute_placeholders(text, args):
    """Replace each #{argname} occurrence with a ${ArgName} variable
    reference. The {} form works in both bash (parameter expansion) and
    PowerShell (delimited variable). Returns text unchanged if no args."""
    if not text or not args:
        return text
    for arg in args:
        placeholder = '#{' + arg['name'] + '}'
        text = text.replace(placeholder, '${' + _shell_safe_name(arg['name']) + '}')
    return text


def _bash_escape_dquoted(s):
    """Escape a string for safe interpolation inside bash double quotes.

    Newlines/tabs/CR are collapsed to a single space so that prompt strings
    stay on a single source line — atomic defaults frequently contain a
    trailing newline that would otherwise produce multi-line `read -p` calls.
    """
    s = s.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    s = s.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
    return s


def _bash_escape_squoted(s):
    """Escape a string for safe interpolation inside bash single quotes."""
    # In single-quoted bash, the only special char is ' itself.
    return s.replace("'", "'\"'\"'")


def _bash_prompt_block(args, indent='            '):
    """Emit bash that prompts for each argument before the test runs.

    Variable name = sanitised argument name. If a default is present we
    show it in the prompt and fall through to it when the user just
    presses Enter.
    """
    if not args:
        return ''
    lines = []
    lines.append(f'{indent}echo -e "${{YELLOW}}Inputs required for this test:${{NC}}"')
    for arg in args:
        var = _shell_safe_name(arg['name'])
        prompt = arg['name']
        if arg['description']:
            prompt += ' — ' + arg['description']
        prompt = _bash_escape_dquoted(prompt)

        if arg['default']:
            default_squoted = _bash_escape_squoted(arg['default'])
            shown_default = _bash_escape_dquoted(arg['default'])
            lines.append(f'{indent}read -p "  {prompt} [{shown_default}]: " _input_{var}')
            lines.append(f"{indent}{var}=\"${{_input_{var}:-{default_squoted}}}\"")
        else:
            lines.append(f'{indent}read -p "  {prompt}: " {var}')
    return '\n'.join(lines) + '\n'


def _powershell_escape_dquoted(s):
    """Escape a string for inclusion inside a PowerShell double-quoted string.

    Control chars (CR/LF/TAB) become PS escape sequences (`r/`n/`t) so that
    the emitted statement stays on one source line. Without this, atomic
    defaults containing a trailing newline produce multi-line "..." strings
    that confuse the Windows PowerShell 5.1 parser and cascade into
    unrelated parse errors further down the script.
    """
    return (s
            .replace('`', '``')
            .replace('"', '`"')
            .replace('$', '`$')
            .replace('\r', '`r')
            .replace('\n', '`n')
            .replace('\t', '`t'))


def _powershell_prompt_block(args, indent='            '):
    """Emit PowerShell that prompts for each argument before the test runs."""
    if not args:
        return ''
    lines = []
    lines.append(f'{indent}Write-Host "Inputs required for this test:" -ForegroundColor Yellow')
    for arg in args:
        var = _shell_safe_name(arg['name'])
        prompt = arg['name']
        if arg['description']:
            prompt += ' — ' + arg['description']
        prompt = _powershell_escape_dquoted(prompt)

        if arg['default']:
            shown_default = _powershell_escape_dquoted(arg['default'])
            # The default value is interpolated via "..." string.
            lines.append(f'{indent}${var} = Read-Host -Prompt "  {prompt} [{shown_default}]"')
            lines.append(f'{indent}if ([string]::IsNullOrEmpty(${var})) {{ ${var} = "{shown_default}" }}')
        else:
            lines.append(f'{indent}${var} = Read-Host -Prompt "  {prompt}"')
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# Safety prompts shared by the generated scripts
# ---------------------------------------------------------------------------
# Every script asks the operator to confirm the target host is in scope
# before anything runs, asks for "RUN ALL" before unattended execution,
# warns about tests that need elevation, defaults cleanup to yes, and
# records which cleanups did not run.


def _missing_inputs(input_args):
    """Names of inputs that have no default (can't run unattended)."""
    return [a['name'] for a in input_args if not a['default']]


def _bash_defaults_block(args, indent='    '):
    """Assign each input its default value (automatic mode)."""
    lines = [f"{indent}{_shell_safe_name(a['name'])}='{_bash_escape_squoted(a['default'])}'" for a in args]
    return '\n'.join(lines) + '\n' if lines else ''


def _powershell_defaults_hashtable(args):
    """PowerShell hashtable literal of input defaults, for Invoke-IsolatedCommand."""
    if not args:
        return '@{}'
    pairs = '; '.join(
        f"'{_shell_safe_name(a['name'])}' = '{a['default'].replace(chr(39), chr(39) * 2)}'" for a in args
    )
    return '@{ ' + pairs + ' }'


def _safety_counts(items):
    elevated = sum(1 for i in items if i.get('elevation_required'))
    cleanup = sum(1 for i in items if i.get('executor_cleanup'))
    return len(items), elevated, cleanup


_BASH_SAFETY = r"""
# --- Safety checks -------------------------------------------------------------
IS_ELEVATED=0
[ "$(id -u)" -eq 0 ] && IS_ELEVATED=1
declare -A CLEANUP

host_addresses() {
    if hostname -I >/dev/null 2>&1; then
        hostname -I
    else
        ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" {print $2}' | tr '\n' ' '
    fi
}

# The operator must confirm this machine is an in-scope target.
# Unattended runs: export PTVAULT_AUTHORIZED_HOST=<this machine's hostname>
confirm_authorization() {
    local host
    host=$(hostname)
    local who
    who=$(id -un)
    local privilege="not root"
    [ "$IS_ELEVATED" -eq 1 ] && privilege="root"
    clear
    echo -e "${RED}+==============================================================+${NC}"
    echo -e "${RED}|${NC}  ${YELLOW}AUTHORIZATION CHECK${NC}"
    echo -e "${RED}+==============================================================+${NC}"
    echo -e "  Plan:        __PLAN__"
    echo -e "  This host:   ${host}"
    echo -e "  Addresses:   $(host_addresses)"
    echo -e "  Running as:  ${who} (${privilege})"
    echo -e "  Tests:       __TOTAL__ (__ELEVATED__ need root, __CLEANUP__ have a cleanup step)"
    echo ""
    echo -e "  ${YELLOW}These tests emulate attacker techniques and change system state.${NC}"
    echo -e "  ${YELLOW}Only run them on systems in scope for an authorised engagement.${NC}"
    echo ""
    if [ -n "${PTVAULT_AUTHORIZED_HOST:-}" ]; then
        if [ "$PTVAULT_AUTHORIZED_HOST" != "$host" ]; then
            echo -e "${RED}PTVAULT_AUTHORIZED_HOST (${PTVAULT_AUTHORIZED_HOST}) does not match this host (${host}). Nothing was run.${NC}"
            exit 1
        fi
        log_event "INFO" "Authorization confirmed via PTVAULT_AUTHORIZED_HOST by ${who} on ${host}"
        return 0
    fi
    local answer
    read -p "Type this machine's hostname (${host}) to confirm it is in scope: " answer
    if [ "$answer" != "$host" ]; then
        echo -e "${RED}Hostname did not match. Nothing was run.${NC}"
        exit 1
    fi
    log_event "INFO" "Authorization confirmed by ${who} on ${host}"
}

# Extra confirmation before running every test without per-test prompts
confirm_automatic() {
    echo ""
    echo -e "${YELLOW}[!] Automatic mode runs all __TOTAL__ tests back to back with no per-test prompt.${NC}"
    echo -e "    Inputs use their default values; tests with a required input that has no default are skipped."
    if [ "$IS_ELEVATED" -ne 1 ] && [ __ELEVATED__ -gt 0 ]; then
        echo -e "    __ELEVATED__ test(s) need root and will be skipped (this session is not root)."
    fi
    echo -e "    Cleanup runs automatically after each test that has one."
    echo ""
    local answer
    read -p "Type RUN ALL to continue, anything else to go back: " answer
    if [ "$answer" != "RUN ALL" ]; then
        echo "Cancelled."
        sleep 1
        return 1
    fi
    log_event "INFO" "Automatic mode confirmed by $(id -un)"
    return 0
}

"""


_POWERSHELL_SAFETY = r"""
# --- Safety checks -------------------------------------------------------------
$global:IsElevated = $false
try {
    $global:IsElevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch {}
$global:Cleanup = @{}

function Get-HostAddresses {
    try {
        $addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | Where-Object { $_.IPAddress -ne '127.0.0.1' } | Select-Object -ExpandProperty IPAddress
    } catch {
        $addrs = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | ForEach-Object { $_.ToString() }
    }
    return ($addrs -join ' ')
}

# The operator must confirm this machine is an in-scope target.
# Unattended runs: $env:PTVAULT_AUTHORIZED_HOST = "<this machine's hostname>"
function Confirm-Authorization {
    $hostName = $env:COMPUTERNAME
    if (-not $hostName) { $hostName = [System.Net.Dns]::GetHostName() }
    $who = $env:USERNAME
    try { $who = [Security.Principal.WindowsIdentity]::GetCurrent().Name } catch {}
    $privilege = if ($global:IsElevated) { "Administrator" } else { "not elevated" }
    Clear-Host
    Write-Host "+==============================================================+" -ForegroundColor Red
    Write-Host "|  AUTHORIZATION CHECK" -ForegroundColor Yellow
    Write-Host "+==============================================================+" -ForegroundColor Red
    Write-Host "  Plan:        __PLAN__"
    Write-Host "  This host:   $hostName"
    Write-Host "  Addresses:   $(Get-HostAddresses)"
    Write-Host "  Running as:  $who ($privilege)"
    Write-Host "  Tests:       __TOTAL__ (__ELEVATED__ need Administrator, __CLEANUP__ have a cleanup step)"
    Write-Host ""
    Write-Host "  These tests emulate attacker techniques and change system state." -ForegroundColor Yellow
    Write-Host "  Only run them on systems in scope for an authorised engagement." -ForegroundColor Yellow
    Write-Host ""
    if ($env:PTVAULT_AUTHORIZED_HOST) {
        if ($env:PTVAULT_AUTHORIZED_HOST -ine $hostName) {
            Write-Host "PTVAULT_AUTHORIZED_HOST ($($env:PTVAULT_AUTHORIZED_HOST)) does not match this host ($hostName). Nothing was run." -ForegroundColor Red
            exit 1
        }
        Write-LogEvent -Level "INFO" -Message "Authorization confirmed via PTVAULT_AUTHORIZED_HOST by $who on $hostName"
        return
    }
    $answer = Read-Host "Type this machine's hostname ($hostName) to confirm it is in scope"
    if ($answer -ine $hostName) {
        Write-Host "Hostname did not match. Nothing was run." -ForegroundColor Red
        exit 1
    }
    Write-LogEvent -Level "INFO" -Message "Authorization confirmed by $who on $hostName"
}

# Extra confirmation before running every test without per-test prompts
function Confirm-Automatic {
    Write-Host ""
    Write-Host "[!] Automatic mode runs all __TOTAL__ tests back to back with no per-test prompt." -ForegroundColor Yellow
    Write-Host "    Inputs use their default values; tests with a required input that has no default are skipped."
    if ((-not $global:IsElevated) -and (__ELEVATED__ -gt 0)) {
        Write-Host "    __ELEVATED__ test(s) need Administrator and will be skipped (this session is not elevated)."
    }
    Write-Host "    Cleanup runs automatically after each test that has one."
    Write-Host ""
    $answer = Read-Host "Type RUN ALL to continue, anything else to go back"
    if ($answer -cne "RUN ALL") {
        Write-Host "Cancelled."
        Start-Sleep -Seconds 1
        return $false
    }
    Write-LogEvent -Level "INFO" -Message "Automatic mode confirmed by $($env:USERNAME)"
    return $true
}

"""


def _fill_safety(template, plan, items, escape):
    total, elevated, cleanup = _safety_counts(items)
    return (template
            .replace('__PLAN__', escape(str(plan.get('name') or 'Unnamed plan')))
            .replace('__TOTAL__', str(total))
            .replace('__ELEVATED__', str(elevated))
            .replace('__CLEANUP__', str(cleanup)))


def _bash_cleanup_summary(items):
    """Bash that lists tests whose cleanup did not run, after the results table."""
    lines = ['    local cleanup_warn=""']
    for idx, item in enumerate(items, 1):
        if not item.get('executor_cleanup'):
            continue
        label = _bash_escape_dquoted(f"[{idx}] {item.get('technique_id') or 'Custom'}: "
                                     f"{item.get('custom_name') or item.get('atomic_test_name') or f'Test {idx}'}")
        lines.append(f'    case "${{CLEANUP["test_{idx}"]:-}}" in SKIPPED|FAILED) '
                     f'cleanup_warn+="  {label} (${{CLEANUP["test_{idx}"]}})\\n" ;; esac')
    lines.append('    if [ -n "$cleanup_warn" ]; then')
    lines.append('        echo -e "${YELLOW}[!] Cleanup did not run for these tests; their artifacts may remain on this system:${NC}"')
    lines.append('        echo -e "$cleanup_warn"')
    lines.append('    fi')
    return '\n'.join(lines) + '\n'


def _powershell_cleanup_summary(items):
    lines = ['    $cleanupWarn = @()']
    for idx, item in enumerate(items, 1):
        if not item.get('executor_cleanup'):
            continue
        label = _powershell_escape_dquoted(f"[{idx}] {item.get('technique_id') or 'Custom'}: "
                                           f"{item.get('custom_name') or item.get('atomic_test_name') or f'Test {idx}'}")
        lines.append(f'    if (@("SKIPPED", "FAILED") -contains $global:Cleanup["Test-{idx}"]) '
                     f'{{ $cleanupWarn += "  {label} ($($global:Cleanup["Test-{idx}"]))" }}')
    lines.append('    if ($cleanupWarn.Count -gt 0) {')
    lines.append('        Write-Host "[!] Cleanup did not run for these tests; their artifacts may remain on this system:" -ForegroundColor Yellow')
    lines.append('        $cleanupWarn | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }')
    lines.append('        Write-Host ""')
    lines.append('    }')
    return '\n'.join(lines) + '\n'


def _bash_automatic_test(idx, total, item):
    """One test in bash automatic mode: defaults for inputs, cleanup after, elevation-aware."""
    func_name = f"test_{idx}"
    raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
    test_name = _bash_escape_dquoted(raw_name)
    technique_id = _bash_escape_dquoted(item.get('technique_id') or 'Custom')
    item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
    is_custom = bool(item.get('custom_command'))
    raw_command = item.get('custom_command') or item.get('executor_command') or 'echo "No command defined"'
    input_args = [] if is_custom else _parse_input_arguments(item.get('input_arguments'))
    exec_command = _substitute_placeholders(raw_command, input_args)
    cleanup_raw = item.get('executor_cleanup') or ''
    missing = _missing_inputs(input_args)

    out = f'''
    # Test {idx}: {technique_id}
    echo ""
    echo -e "${{CYAN}}================================================================================${{NC}}"
    echo -e "${{CYAN}}|${{NC}} ${{BLUE}}TEST {idx} of {total}${{NC}}"
    echo -e "${{CYAN}}|${{NC}} ${{YELLOW}}Technique:${{NC}} {technique_id}"
    echo -e "${{CYAN}}|${{NC}} ${{YELLOW}}Test Name:${{NC}} {test_name}"
    echo -e "${{CYAN}}================================================================================${{NC}}"
'''
    if missing:
        names = _bash_escape_dquoted(', '.join(missing))
        return out + f'''    log_event "SKIP" "Test {idx} skipped (needs input with no default: {names}): {technique_id}{item_tag}"
    RESULTS["{func_name}"]="SKIPPED"
'''

    run = f'''{_bash_defaults_block(input_args)}    START_TIMES["{func_name}"]=$(date +%s)
    log_event "START" "Executing test {idx}: {technique_id} - {test_name}{item_tag}"
    echo -e "${{CYAN}}--- Command Output -------------------------------------------${{NC}}"
{exec_command}
    local exit_code_{idx}=$?
    echo -e "${{CYAN}}--------------------------------------------------------------${{NC}}"
    END_TIMES["{func_name}"]=$(date +%s)
    local duration_{idx}=$((END_TIMES["{func_name}"] - START_TIMES["{func_name}"]))
    if [ $exit_code_{idx} -eq 0 ]; then
        log_event "PASS" "Test {idx} completed successfully (exit code: $exit_code_{idx}, duration: ${{duration_{idx}}}s){item_tag}"
        RESULTS["{func_name}"]="PASSED"
    else
        log_event "FAIL" "Test {idx} failed (exit code: $exit_code_{idx}, duration: ${{duration_{idx}}}s){item_tag}"
        RESULTS["{func_name}"]="FAILED"
    fi
    log_event "END" "Finished test {idx}: {technique_id}{item_tag}"
'''
    if cleanup_raw:
        exec_cleanup = _substitute_placeholders(cleanup_raw, input_args)
        run += f'''    echo -e "${{YELLOW}}[*] Running cleanup...${{NC}}"
{exec_cleanup}
    if [ $? -eq 0 ]; then
        CLEANUP["{func_name}"]="DONE"
        log_event "INFO" "Cleanup completed for test {idx}: {technique_id}{item_tag}"
    else
        CLEANUP["{func_name}"]="FAILED"
        log_event "INFO" "Cleanup failed for test {idx}: {technique_id} - artifacts may remain{item_tag}"
    fi
'''
    if item.get('elevation_required'):
        return out + f'''    if [ "$IS_ELEVATED" -ne 1 ]; then
        log_event "SKIP" "Test {idx} skipped (requires root): {technique_id}{item_tag}"
        RESULTS["{func_name}"]="SKIPPED"
    else
{run}    fi
'''
    return out + run


def _powershell_automatic_test(idx, total, item):
    """One test in PowerShell automatic mode: defaults for inputs, cleanup after, elevation-aware."""
    import base64
    func_name = f"Test-{idx}"
    raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
    test_name = _powershell_escape_dquoted(raw_name)
    technique_id = _powershell_escape_dquoted(item.get('technique_id') or 'Custom')
    item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
    is_custom = bool(item.get('custom_command'))
    raw_command = item.get('custom_command') or item.get('executor_command') or 'Write-Host "No command defined"'
    input_args = [] if is_custom else _parse_input_arguments(item.get('input_arguments'))
    exec_command = _substitute_placeholders(raw_command, input_args)
    command_b64 = base64.b64encode(exec_command.encode('utf-8')).decode('ascii')
    variables = _powershell_defaults_hashtable(input_args)
    cleanup_raw = item.get('executor_cleanup') or ''
    missing = _missing_inputs(input_args)

    out = f'''
    # Test {idx}: {technique_id}
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "| TEST {idx} of {total}" -ForegroundColor Blue
    Write-Host "| Technique: " -ForegroundColor Cyan -NoNewline; Write-Host "{technique_id}" -ForegroundColor Yellow
    Write-Host "| Test Name: " -ForegroundColor Cyan -NoNewline; Write-Host "{test_name}" -ForegroundColor Yellow
    Write-Host "================================================================================" -ForegroundColor Cyan
'''
    if missing:
        names = _powershell_escape_dquoted(', '.join(missing))
        return out + f'''    Write-LogEvent -Level "SKIP" -Message "Test {idx} skipped (needs input with no default: {names}): {technique_id}{item_tag}"
    $global:Results["{func_name}"] = "SKIPPED"
'''

    run = f'''    $autoVars = {variables}
    $global:StartTimes["{func_name}"] = Get-Date
    Write-LogEvent -Level "START" -Message "Executing test {idx}: {technique_id} - {test_name}{item_tag}"
    Write-Host "--- Command Output -------------------------------------------" -ForegroundColor Cyan
    try {{
        $batchCmd = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{command_b64}"))
        # Child process isolates `exit` so a single broken atomic can't abort the batch.
        $exitCode = Invoke-IsolatedCommand -Command $batchCmd -Variables $autoVars
        Write-Host "--------------------------------------------------------------" -ForegroundColor Cyan
        $global:EndTimes["{func_name}"] = Get-Date
        $duration = ($global:EndTimes["{func_name}"] - $global:StartTimes["{func_name}"]).TotalSeconds
        if ($exitCode -eq 0) {{
            Write-LogEvent -Level "PASS" -Message "Test {idx} completed successfully (duration: $([math]::Round($duration,1))s){item_tag}"
            $global:Results["{func_name}"] = "PASSED"
        }} else {{
            Write-LogEvent -Level "FAIL" -Message "Test {idx} failed (exit code: $exitCode, duration: $([math]::Round($duration,1))s){item_tag}"
            $global:Results["{func_name}"] = "FAILED"
        }}
    }} catch {{
        Write-Host "--------------------------------------------------------------" -ForegroundColor Cyan
        $global:EndTimes["{func_name}"] = Get-Date
        $duration = ($global:EndTimes["{func_name}"] - $global:StartTimes["{func_name}"]).TotalSeconds
        Write-LogEvent -Level "FAIL" -Message "Test {idx} failed: $_ (duration: $([math]::Round($duration,1))s){item_tag}"
        $global:Results["{func_name}"] = "FAILED"
    }}
    Write-LogEvent -Level "END" -Message "Finished test {idx}: {technique_id}{item_tag}"
'''
    if cleanup_raw:
        cleanup_b64 = base64.b64encode(
            _substitute_placeholders(cleanup_raw, input_args).encode('utf-8')).decode('ascii')
        run += f'''    Write-Host "[*] Running cleanup..." -ForegroundColor Yellow
    try {{
        $cleanupCmd = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{cleanup_b64}"))
        $cleanupExit = Invoke-IsolatedCommand -Command $cleanupCmd -Variables $autoVars
        if ($cleanupExit -eq 0) {{
            $global:Cleanup["{func_name}"] = "DONE"
            Write-LogEvent -Level "INFO" -Message "Cleanup completed for test {idx}: {technique_id}{item_tag}"
        }} else {{
            $global:Cleanup["{func_name}"] = "FAILED"
            Write-LogEvent -Level "INFO" -Message "Cleanup failed for test {idx}: {technique_id} - artifacts may remain{item_tag}"
        }}
    }} catch {{
        $global:Cleanup["{func_name}"] = "FAILED"
        Write-LogEvent -Level "INFO" -Message "Cleanup failed for test {idx}: {technique_id} - artifacts may remain{item_tag}"
    }}
'''
    if item.get('elevation_required'):
        return out + f'''    if (-not $global:IsElevated) {{
        Write-LogEvent -Level "SKIP" -Message "Test {idx} skipped (requires Administrator): {technique_id}{item_tag}"
        $global:Results["{func_name}"] = "SKIPPED"
    }} else {{
{run}    }}
'''
    return out + run


def generate_script(plan, items, platform='bash'):
    """
    Generate an executable script from a test plan.

    Args:
        plan: Test plan dict with name, description
        items: List of test plan items with atomic details
        platform: 'bash' or 'powershell'

    Returns:
        str: Complete script content
    """
    if platform == 'powershell':
        return generate_powershell_script(plan, items)
    else:
        return generate_bash_script(plan, items)


def generate_bash_script(plan, items):
    """Generate a Bash script with interactive menu."""

    # Filter items for bash-compatible platforms
    compatible_items = []
    for item in items:
        if not item.get('enabled', True):
            continue
        platforms = item.get('supported_platforms', [])
        if isinstance(platforms, str):
            try:
                import json
                platforms = json.loads(platforms)
            except (json.JSONDecodeError, ValueError):
                platforms = [platforms]
        # Include if linux, macos, or custom test (no platforms specified)
        if not platforms or 'linux' in platforms or 'macos' in platforms:
            compatible_items.append(item)

    script = f'''#!/bin/bash
# ============================================================================
# PTVault Test Plan: {plan.get('name', 'Unnamed Plan')}
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ============================================================================
# Description: {plan.get('description', 'No description')}
# Total Tests: {len(compatible_items)}
# ============================================================================
#
# WARNING: This script contains commands that may modify system state.
# Only run this on authorized test systems.
#
# ============================================================================

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
CYAN='\\033[0;36m'
MAGENTA='\\033[0;35m'
NC='\\033[0m' # No Color

# Results tracking
declare -A RESULTS
declare -A START_TIMES
declare -A END_TIMES

# Timestamp function for log correlation
timestamp() {{
    date '+%Y-%m-%d %H:%M:%S'
}}

# Log function with timestamp
log_event() {{
    local level="$1"
    local message="$2"
    local ts=$(timestamp)
    case $level in
        "START")
            echo -e "${{MAGENTA}}[$ts]${{NC}} ${{GREEN}}[START]${{NC}} $message"
            ;;
        "END")
            echo -e "${{MAGENTA}}[$ts]${{NC}} ${{BLUE}}[END]${{NC}} $message"
            ;;
        "EXEC")
            echo -e "${{MAGENTA}}[$ts]${{NC}} ${{YELLOW}}[EXEC]${{NC}} $message"
            ;;
        "INFO")
            echo -e "${{MAGENTA}}[$ts]${{NC}} ${{CYAN}}[INFO]${{NC}} $message"
            ;;
        "PASS")
            echo -e "${{MAGENTA}}[$ts]${{NC}} ${{GREEN}}[PASS]${{NC}} $message"
            ;;
        "FAIL")
            echo -e "${{MAGENTA}}[$ts]${{NC}} ${{RED}}[FAIL]${{NC}} $message"
            ;;
        "SKIP")
            echo -e "${{MAGENTA}}[$ts]${{NC}} ${{YELLOW}}[SKIP]${{NC}} $message"
            ;;
        *)
            echo -e "${{MAGENTA}}[$ts]${{NC}} $message"
            ;;
    esac
}}

# Test functions
'''

    script += _fill_safety(_BASH_SAFETY, plan, compatible_items, _bash_escape_dquoted)

    # Generate function for each test
    for idx, item in enumerate(compatible_items, 1):
        func_name = f"test_{idx}"
        raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
        raw_technique = item.get('technique_id') or 'Custom'
        test_name = _bash_escape_dquoted(raw_name)
        technique_id = _bash_escape_dquoted(raw_technique)
        # Machine-readable tag so PTVault can map log lines back to plan items
        item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
        raw_command = item.get('custom_command') or item.get('executor_command') or 'echo "No command defined"'
        cleanup_raw = item.get('executor_cleanup', '')

        # Parse input arguments. Custom (manually-edited) commands skip
        # placeholder substitution because users may want literal #{...}.
        is_custom = bool(item.get('custom_command'))
        input_args = [] if is_custom else _parse_input_arguments(item.get('input_arguments'))

        # Display version keeps original #{argname} so the user sees the
        # canonical Atomic command. Execution version substitutes ${ArgName}.
        display_command = raw_command.replace("'", "'\"'\"'")
        exec_command = _substitute_placeholders(raw_command, input_args)
        prompts = _bash_prompt_block(input_args)
        elevation_note = (
            '    if [ "$IS_ELEVATED" -ne 1 ]; then\n'
            '        echo -e "${YELLOW}[!] This test requires root; this session is not root, so it will probably fail.${NC}"\n'
            '        echo ""\n'
            '    fi\n'
        ) if item.get('elevation_required') else ''

        script += f'''
{func_name}() {{
    echo ""
    echo -e "${{CYAN}}=============================================================================${{NC}}"
    echo -e "${{CYAN}}|${{NC}} ${{BLUE}}TEST {idx} of {len(compatible_items)}${{NC}}"
    echo -e "${{CYAN}}|${{NC}} ${{YELLOW}}Technique:${{NC}} {technique_id}"
    echo -e "${{CYAN}}|${{NC}} ${{YELLOW}}Test Name:${{NC}} {test_name}"
    echo -e "${{CYAN}}=============================================================================${{NC}}"
    echo ""
    log_event "INFO" "Preparing test: {technique_id} - {test_name}"
    echo ""
{elevation_note}    echo -e "${{YELLOW}}Command to execute:${{NC}}"
    echo -e "${{CYAN}}-------------------------------------------------------------${{NC}}"
    echo '{display_command}'
    echo -e "${{CYAN}}-------------------------------------------------------------${{NC}}"
    echo ""
    read -p "Execute this test? [y/N/s(kip)] " confirm
    case $confirm in
        [Yy]* )
{prompts}            START_TIMES["{func_name}"]=$(date +%s)
            log_event "START" "Executing test {idx}: {technique_id} - {test_name}{item_tag}"
            echo ""
            echo -e "${{CYAN}}--- Command Output ----------------------------------------------${{NC}}"
            # Execute the command (with #{{argname}} placeholders substituted from prompts)
            {exec_command}
            local exit_code=$?
            echo -e "${{CYAN}}-----------------------------------------------------------------${{NC}}"
            echo ""
            END_TIMES["{func_name}"]=$(date +%s)
            local duration=$((END_TIMES["{func_name}"] - START_TIMES["{func_name}"]))
            if [ $exit_code -eq 0 ]; then
                log_event "PASS" "Test {idx} completed successfully (exit code: $exit_code, duration: ${{duration}}s){item_tag}"
                RESULTS["{func_name}"]="PASSED"
            else
                log_event "FAIL" "Test {idx} failed (exit code: $exit_code, duration: ${{duration}}s){item_tag}"
                RESULTS["{func_name}"]="FAILED"
            fi
            log_event "END" "Finished test {idx}: {technique_id}{item_tag}"
'''

        if cleanup_raw:
            exec_cleanup = _substitute_placeholders(cleanup_raw, input_args)
            script += f'''
            read -p "Run cleanup command? [Y/n] " do_cleanup
            if [[ ! $do_cleanup =~ ^[Nn] ]]; then
                echo -e "${{YELLOW}}[*] Running cleanup...${{NC}}"
{exec_cleanup}
                if [ $? -eq 0 ]; then
                    CLEANUP["{func_name}"]="DONE"
                    log_event "INFO" "Cleanup completed for test {idx}: {technique_id}{item_tag}"
                else
                    CLEANUP["{func_name}"]="FAILED"
                    log_event "INFO" "Cleanup failed for test {idx}: {technique_id} - artifacts may remain{item_tag}"
                fi
            else
                CLEANUP["{func_name}"]="SKIPPED"
                log_event "INFO" "Cleanup skipped for test {idx}: {technique_id} - artifacts may remain{item_tag}"
            fi
'''

        script += f'''            ;;
        [Ss]* )
            log_event "SKIP" "Test {idx} skipped by user: {technique_id}{item_tag}"
            RESULTS["{func_name}"]="SKIPPED"
            ;;
        * )
            log_event "SKIP" "Test {idx} skipped: {technique_id}{item_tag}"
            RESULTS["{func_name}"]="SKIPPED"
            ;;
    esac
    echo ""
}}

'''

    # Add menu and main function
    script += '''
show_menu() {
    clear
    echo -e "${CYAN}+==============================================================+${NC}"
    echo -e "${CYAN}|${NC}           ${BLUE}PTVault Test Plan Execution Menu${NC}               ${CYAN}|${NC}"
    echo -e "${CYAN}+==============================================================+${NC}"
'''

    script += f'    echo -e "${{CYAN}}|${{NC}}  Plan: {plan.get("name", "Unnamed")[:50]:<52} ${{CYAN}}|${{NC}}"\n'
    script += '''    echo -e "${CYAN}+==============================================================+${NC}"
    echo ""
'''

    for idx, item in enumerate(compatible_items, 1):
        raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
        raw_technique = item.get('technique_id') or 'Custom'
        test_name = _bash_escape_dquoted(raw_name)
        technique_id = _bash_escape_dquoted(raw_technique)
        # Machine-readable tag so PTVault can map log lines back to plan items
        item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
        display_name = _bash_escape_dquoted(f"{raw_technique}: {raw_name}"[:55])
        script += f'    echo -e "  ${{BLUE}}[{idx}]${{NC}} {display_name}"\n'

    script += f'''    echo ""
    echo -e "  ${{GREEN}}[A]${{NC}} Run ALL tests"
    echo -e "  ${{YELLOW}}[R]${{NC}} Show results summary"
    echo -e "  ${{CYAN}}[B]${{NC}} Back to mode selection"
    echo -e "  ${{RED}}[Q]${{NC}} Quit"
    echo ""
    echo -e "${{CYAN}}+==============================================================+${{NC}}"
}}

show_results() {{
    echo ""
    echo -e "${{CYAN}}================================================================================${{NC}}"
    echo -e "${{BLUE}}                           RESULTS SUMMARY${{NC}}"
    echo -e "${{MAGENTA}}                    Generated: $(timestamp)${{NC}}"
    echo -e "${{CYAN}}================================================================================${{NC}}"
    echo ""
    local passed=0
    local failed=0
    local skipped=0
'''

    for idx, item in enumerate(compatible_items, 1):
        func_name = f"test_{idx}"
        raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
        raw_technique = item.get('technique_id') or 'Custom'
        test_name = _bash_escape_dquoted(raw_name)
        technique_id = _bash_escape_dquoted(raw_technique)
        # Machine-readable tag so PTVault can map log lines back to plan items
        item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
        script += f'''    result="${{RESULTS["{func_name}"]:-NOT RUN}}"
    case $result in
        "PASSED") echo -e "  ${{GREEN}}[PASS]${{NC}} [{idx}] {technique_id}: {test_name}"; ((passed++)) ;;
        "FAILED") echo -e "  ${{RED}}[FAIL]${{NC}} [{idx}] {technique_id}: {test_name}"; ((failed++)) ;;
        "SKIPPED") echo -e "  ${{YELLOW}}[SKIP]${{NC}} [{idx}] {technique_id}: {test_name}"; ((skipped++)) ;;
        *) echo -e "  ${{CYAN}}[----]${{NC}} [{idx}] {technique_id}: {test_name}" ;;
    esac
'''

    script += f'''    echo ""
    echo -e "${{CYAN}}============================================================${{NC}}"
    echo -e "  Total: {len(compatible_items)} | ${{GREEN}}Passed: $passed${{NC}} | ${{RED}}Failed: $failed${{NC}} | ${{YELLOW}}Skipped: $skipped${{NC}}"
    echo -e "${{CYAN}}============================================================${{NC}}"
    echo ""
{_bash_cleanup_summary(compatible_items)}    read -p "Press Enter to continue..."
}}

run_all() {{
    log_event "START" "Beginning batch execution of all {len(compatible_items)} tests"
    echo ""
    echo -e "${{CYAN}}+==============================================================+${{NC}}"
    echo -e "${{CYAN}}|${{NC}}        ${{YELLOW}}BATCH EXECUTION - {len(compatible_items)} TESTS${{NC}}                         ${{CYAN}}|${{NC}}"
    echo -e "${{CYAN}}+==============================================================+${{NC}}"
    echo ""
    local batch_start=$(date +%s)
'''

    for idx in range(1, len(compatible_items) + 1):
        script += f"    test_{idx}\n"

    script += '''    local batch_end=$(date +%s)
    local batch_duration=$((batch_end - batch_start))
    echo ""
    log_event "END" "Batch execution completed (total duration: ${batch_duration}s)"
    show_results
}

# Run tests sequentially with prompts
run_sequential() {
'''
    script += f'    log_event "START" "Beginning sequential execution of {len(compatible_items)} tests"\n    echo ""\n'

    for idx in range(1, len(compatible_items) + 1):
        script += f"    test_{idx}\n"

    script += '''    echo ""
    log_event "END" "Sequential execution completed"
    show_results
}

# Run every test without per-test prompts (gated by confirm_automatic)
run_automatic() {
'''
    script += f'''    log_event "START" "Beginning automatic execution of all {len(compatible_items)} tests"
    echo ""
    echo -e "${{CYAN}}+==============================================================+${{NC}}"
    echo -e "${{CYAN}}|${{NC}}     ${{YELLOW}}AUTOMATIC EXECUTION MODE - {len(compatible_items)} TESTS${{NC}}"
    echo -e "${{CYAN}}|${{NC}}     ${{BLUE}}Default inputs, cleanup after each test${{NC}}"
    echo -e "${{CYAN}}+==============================================================+${{NC}}"
    echo ""
    local batch_start=$(date +%s)
'''

    for idx, item in enumerate(compatible_items, 1):
        script += _bash_automatic_test(idx, len(compatible_items), item)

    script += '''
    local batch_end=$(date +%s)
    local batch_duration=$((batch_end - batch_start))
    echo ""
    log_event "END" "Automatic execution completed (total duration: ${batch_duration}s)"
    show_results
}

# Execution mode selection
select_execution_mode() {
    clear
    echo -e "${CYAN}+==============================================================+${NC}"
    echo -e "${CYAN}|${NC}           ${BLUE}PTVault Test Plan Execution${NC}                      ${CYAN}|${NC}"
    echo -e "${CYAN}+==============================================================+${NC}"
'''

    script += f'    echo -e "${{CYAN}}|${{NC}}  Plan: {plan.get("name", "Unnamed")[:50]:<52} ${{CYAN}}|${{NC}}"\n'
    script += f'    echo -e "${{CYAN}}|${{NC}}  Tests: {len(compatible_items):<53} ${{CYAN}}|${{NC}}"\n'

    script += '''    echo -e "${CYAN}+==============================================================+${NC}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}  ${YELLOW}How would you like to run the tests?${NC}                       ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}  ${GREEN}[1]${NC} Run ALL tests automatically                            ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}      No per-test prompts; asks you to type RUN ALL           ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}  ${BLUE}[2]${NC} Run tests ONE AT A TIME                                ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}      Prompt before each test execution                       ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}  ${YELLOW}[3]${NC} Interactive menu                                       ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}      Choose which tests to run from a menu                   ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}  ${RED}[Q]${NC} Quit                                                   ${CYAN}|${NC}"
    echo -e "${CYAN}|${NC}                                                              ${CYAN}|${NC}"
    echo -e "${CYAN}+==============================================================+${NC}"
    echo ""
    read -p "Select execution mode [1/2/3/Q]: " mode
    case $mode in
        1)
            if confirm_automatic; then
                run_automatic
            else
                select_execution_mode
            fi
            ;;
        2)
            run_sequential
            ;;
        3)
            interactive_menu
            ;;
        [Qq])
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            sleep 1
            select_execution_mode
            ;;
    esac
}

# Interactive menu loop
interactive_menu() {
    while true; do
        show_menu
        read -p "Select option: " choice
        case $choice in
'''

    for idx in range(1, len(compatible_items) + 1):
        script += f'            {idx}) test_{idx}; read -p "Press Enter to continue..." ;;\n'

    script += '''            [Aa]) run_all ;;
            [Rr]) show_results ;;
            [Bb]) select_execution_mode ;;
            [Qq]) echo "Goodbye!"; exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}"; sleep 1 ;;
        esac
    done
}

# Confirm this host is in scope, then choose how to run
confirm_authorization
select_execution_mode
'''

    return script


def generate_powershell_script(plan, items):
    """Generate a PowerShell script with interactive menu.

    The returned string starts with U+FEFF so the UTF-8 encoding includes
    a BOM. Windows PowerShell 5.1 reads BOM-less files using the system
    ANSI codepage (cp1252 on US/EU systems); under cp1252 the third byte
    of an em-dash (UTF-8 E2 80 94) becomes U+201D — a smart close-quote —
    which Windows PowerShell treats as a string delimiter and uses to
    prematurely terminate every Read-Host -Prompt "..." string. With a
    BOM, the file is read as UTF-8 and em-dashes survive intact.
    """

    # Filter items for Windows-compatible platforms
    compatible_items = []
    for item in items:
        if not item.get('enabled', True):
            continue
        platforms = item.get('supported_platforms', [])
        if isinstance(platforms, str):
            try:
                import json
                platforms = json.loads(platforms)
            except (json.JSONDecodeError, ValueError):
                platforms = [platforms]
        # Include if windows or custom test (no platforms specified)
        if not platforms or 'windows' in platforms:
            compatible_items.append(item)

    script = f'''﻿# ============================================================================
# PTVault Test Plan: {plan.get('name', 'Unnamed Plan')}
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ============================================================================
# Description: {plan.get('description', 'No description')}
# Total Tests: {len(compatible_items)}
# ============================================================================
#
# WARNING: This script contains commands that may modify system state.
# Only run this on authorized test systems.
#
# ============================================================================

# Results tracking
$global:Results = @{{}}
$global:StartTimes = @{{}}
$global:EndTimes = @{{}}

# Timestamp function for log correlation
function Get-Timestamp {{
    return (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
}}

# Log function with timestamp
function Write-LogEvent {{
    param(
        [string]$Level,
        [string]$Message
    )
    $ts = Get-Timestamp
    switch ($Level) {{
        "START" {{ Write-Host "[$ts] " -ForegroundColor Magenta -NoNewline; Write-Host "[START] " -ForegroundColor Green -NoNewline; Write-Host $Message }}
        "END"   {{ Write-Host "[$ts] " -ForegroundColor Magenta -NoNewline; Write-Host "[END] " -ForegroundColor Blue -NoNewline; Write-Host $Message }}
        "EXEC"  {{ Write-Host "[$ts] " -ForegroundColor Magenta -NoNewline; Write-Host "[EXEC] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }}
        "INFO"  {{ Write-Host "[$ts] " -ForegroundColor Magenta -NoNewline; Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline; Write-Host $Message }}
        "PASS"  {{ Write-Host "[$ts] " -ForegroundColor Magenta -NoNewline; Write-Host "[PASS] " -ForegroundColor Green -NoNewline; Write-Host $Message }}
        "FAIL"  {{ Write-Host "[$ts] " -ForegroundColor Magenta -NoNewline; Write-Host "[FAIL] " -ForegroundColor Red -NoNewline; Write-Host $Message }}
        "SKIP"  {{ Write-Host "[$ts] " -ForegroundColor Magenta -NoNewline; Write-Host "[SKIP] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }}
        default {{ Write-Host "[$ts] $Message" -ForegroundColor Magenta }}
    }}
}}

# Run an atomic command in an isolated child PowerShell process. Some atomics
# call `exit` to surface an HRESULT (e.g. T1018 Get-WmiObject DC enumeration);
# inside Invoke-Expression that would terminate THIS wrapper script and lose
# all accumulated results. Spawning a child process scopes `exit` to the
# child, preserves output streaming via -NoNewWindow, and returns the real
# exit code so the wrapper can mark PASS/FAIL.
#
# The TimeoutSeconds default of 180 (3 minutes) covers GUI-automation atomics
# (e.g. T1059.001 Mimikatz - Cradlecraft PsSendKeys) that drive Notepad via
# SendKeys and hang forever on modern Windows where the legacy "open from
# URL" behavior is gone. When the timeout fires we taskkill /T the child so
# any spawned GUI processes (Notepad, Explorer, etc.) die with it, and we
# return exit code 124 — the POSIX convention for timeout — so the wrapper
# marks the test FAILED and moves on.
function Invoke-IsolatedCommand {{
    param(
        [string]$Command,
        [hashtable]$Variables = @{{}},
        [int]$TimeoutSeconds = 180
    )

    # Build a prologue that recreates each prompted variable in the child
    # using a single-quoted literal (no expansion). Single quotes inside the
    # value are doubled for PS escape conventions.
    $prologueLines = @()
    foreach ($entry in $Variables.GetEnumerator()) {{
        $val = if ($null -eq $entry.Value) {{ "" }} else {{ [string]$entry.Value }}
        $escaped = $val -replace "'", "''"
        $prologueLines += ("`$" + $entry.Key + " = '" + $escaped + "'")
    }}
    $fullScript = ($prologueLines -join "`r`n") + "`r`n" + $Command

    # Write UTF-8 with BOM so Windows PowerShell 5.1 reads non-ASCII intact.
    $tmpPath = [IO.Path]::Combine(
        [IO.Path]::GetTempPath(),
        "ptvault_" + [Guid]::NewGuid().ToString("N") + ".ps1"
    )
    $utf8Bom = [Text.UTF8Encoding]::new($true)
    [IO.File]::WriteAllText($tmpPath, $fullScript, $utf8Bom)

    try {{
        # Start via [Diagnostics.Process]::Start with a ProcessStartInfo we
        # own. Start-Process -PassThru on Windows PowerShell 5.1 returns a
        # Process whose handle gets closed when the child exits, so its
        # .ExitCode reads as $null for fast-running atomics — which would
        # make every test fail PASS/FAIL parity (we'd compare $null -eq 0).
        # Owning the Process object keeps the handle open until we read it.
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "powershell.exe"
        $psi.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $tmpPath + '"'
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $false
        $psi.RedirectStandardOutput = $false
        $psi.RedirectStandardError = $false
        $psi.RedirectStandardInput = $false
        $proc = [System.Diagnostics.Process]::Start($psi)
        $exited = $proc.WaitForExit($TimeoutSeconds * 1000)
        if (-not $exited) {{
            Write-Host ""
            Write-Host "[!] Test exceeded $TimeoutSeconds s timeout - terminating child process tree" -ForegroundColor Red
            # taskkill /T recursively kills the child PowerShell plus anything
            # it spawned (Notepad, Explorer windows, mshta, etc.).
            & taskkill.exe /T /F /PID $proc.Id 2>&1 | Out-Null
            try {{ $proc.WaitForExit(5000) | Out-Null }} catch {{}}
            return 124
        }}
        return $proc.ExitCode
    }} finally {{
        Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
    }}
}}

'''

    script += _fill_safety(_POWERSHELL_SAFETY, plan, compatible_items, _powershell_escape_dquoted)

    # Generate function for each test
    for idx, item in enumerate(compatible_items, 1):
        func_name = f"Test-{idx}"
        raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
        raw_technique = item.get('technique_id') or 'Custom'
        test_name = _powershell_escape_dquoted(raw_name)
        technique_id = _powershell_escape_dquoted(raw_technique)
        # Machine-readable tag so PTVault can map log lines back to plan items
        item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
        raw_command = item.get('custom_command') or item.get('executor_command') or 'Write-Host "No command defined"'
        cleanup_raw = item.get('executor_cleanup', '')

        is_custom = bool(item.get('custom_command'))
        input_args = [] if is_custom else _parse_input_arguments(item.get('input_arguments'))

        # Display version preserves the original #{argname} placeholders
        # so the user sees the canonical Atomic command. Execution version
        # has them substituted with ${ArgName} so PowerShell expands them.
        exec_command = _substitute_placeholders(raw_command, input_args)

        # Use Base64 encoding to avoid PowerShell parsing issues
        import base64
        display_bytes = raw_command.encode('utf-8')
        command_display_base64 = base64.b64encode(display_bytes).decode('ascii')
        exec_bytes = exec_command.encode('utf-8')
        command_base64 = base64.b64encode(exec_bytes).decode('ascii')

        prompts = _powershell_prompt_block(input_args)
        elevation_note = (
            '    if (-not $global:IsElevated) {\n'
            '        Write-Host "[!] This test requires Administrator; this session is not elevated, so it will probably fail." -ForegroundColor Yellow\n'
            '        Write-Host ""\n'
            '    }\n'
        ) if item.get('elevation_required') else ''
        var_names = [_shell_safe_name(a['name']) for a in input_args]
        if var_names:
            promptvars_init = '\n'.join(
                f"            $_promptVars['{name}'] = ${name}" for name in var_names
            ) + '\n'
        else:
            promptvars_init = ''

        script += f'''
function {func_name} {{
    Write-Host ""
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host "| TEST {idx} of {len(compatible_items)}" -ForegroundColor Blue
    Write-Host "| Technique: " -ForegroundColor Cyan -NoNewline; Write-Host "{technique_id}" -ForegroundColor Yellow
    Write-Host "| Test Name: " -ForegroundColor Cyan -NoNewline; Write-Host "{test_name}" -ForegroundColor Yellow
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-LogEvent -Level "INFO" -Message "Preparing test: {technique_id} - {test_name}"
    Write-Host ""
{elevation_note}    Write-Host "Command to execute:" -ForegroundColor Yellow
    Write-Host "-------------------------------------------------------------" -ForegroundColor Cyan
    # Decode and display command
    $displayBase64 = "{command_display_base64}"
    $displayBytes = [System.Convert]::FromBase64String($displayBase64)
    $displayCmd = [System.Text.Encoding]::UTF8.GetString($displayBytes)
    Write-Host $displayCmd
    Write-Host "-------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host ""

    $confirm = Read-Host "Execute this test? [y/N/s(kip)]"
    switch -Regex ($confirm) {{
        "^[Yy]" {{
            $_promptVars = @{{}}
{prompts}{promptvars_init}            $global:StartTimes["{func_name}"] = Get-Date
            Write-LogEvent -Level "START" -Message "Executing test {idx}: {technique_id} - {test_name}{item_tag}"
            Write-Host ""
            Write-Host "--- Command Output ----------------------------------------------" -ForegroundColor Cyan
            try {{
                # Decode Base64 command (with #{{argname}} → ${{ArgName}} substituted from prompts)
                $commandBase64 = "{command_base64}"
                $commandBytes = [System.Convert]::FromBase64String($commandBase64)
                $command = [System.Text.Encoding]::UTF8.GetString($commandBytes)
                # Run in a child process so `exit` in the atomic can't kill us.
                $exitCode = Invoke-IsolatedCommand -Command $command -Variables $_promptVars
                Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
                Write-Host ""
                $global:EndTimes["{func_name}"] = Get-Date
                $duration = ($global:EndTimes["{func_name}"] - $global:StartTimes["{func_name}"]).TotalSeconds
                if ($exitCode -eq 0) {{
                    Write-LogEvent -Level "PASS" -Message "Test {idx} completed successfully (duration: $([math]::Round($duration,1))s){item_tag}"
                    $global:Results["{func_name}"] = "PASSED"
                }} else {{
                    Write-LogEvent -Level "FAIL" -Message "Test {idx} failed (exit code: $exitCode, duration: $([math]::Round($duration,1))s){item_tag}"
                    $global:Results["{func_name}"] = "FAILED"
                }}
            }} catch {{
                Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
                Write-Host ""
                $global:EndTimes["{func_name}"] = Get-Date
                $duration = ($global:EndTimes["{func_name}"] - $global:StartTimes["{func_name}"]).TotalSeconds
                Write-LogEvent -Level "FAIL" -Message "Test {idx} failed: $_ (duration: $([math]::Round($duration,1))s){item_tag}"
                $global:Results["{func_name}"] = "FAILED"
            }}
            Write-LogEvent -Level "END" -Message "Finished test {idx}: {technique_id}{item_tag}"
'''

        if cleanup_raw:
            import base64
            exec_cleanup = _substitute_placeholders(cleanup_raw, input_args)
            cleanup_bytes = exec_cleanup.encode('utf-8')
            cleanup_base64 = base64.b64encode(cleanup_bytes).decode('ascii')
            script += f'''
            $doCleanup = Read-Host "Run cleanup command? [Y/n]"
            if ($doCleanup -notmatch "^[Nn]") {{
                Write-Host "[*] Running cleanup..." -ForegroundColor Yellow
                try {{
                    $cleanupBase64 = "{cleanup_base64}"
                    $cleanupBytes = [System.Convert]::FromBase64String($cleanupBase64)
                    $cleanupCmd = [System.Text.Encoding]::UTF8.GetString($cleanupBytes)
                    # Same isolation as the test command — cleanup can also `exit`.
                    $cleanupExit = Invoke-IsolatedCommand -Command $cleanupCmd -Variables $_promptVars
                    if ($cleanupExit -eq 0) {{
                        $global:Cleanup["{func_name}"] = "DONE"
                        Write-LogEvent -Level "INFO" -Message "Cleanup completed for test {idx}: {technique_id}{item_tag}"
                    }} else {{
                        $global:Cleanup["{func_name}"] = "FAILED"
                        Write-LogEvent -Level "INFO" -Message "Cleanup failed for test {idx}: {technique_id} - artifacts may remain{item_tag}"
                    }}
                }} catch {{
                    $global:Cleanup["{func_name}"] = "FAILED"
                    Write-Host "Cleanup failed: $_" -ForegroundColor Red
                    Write-LogEvent -Level "INFO" -Message "Cleanup failed for test {idx}: {technique_id} - artifacts may remain{item_tag}"
                }}
            }} else {{
                $global:Cleanup["{func_name}"] = "SKIPPED"
                Write-LogEvent -Level "INFO" -Message "Cleanup skipped for test {idx}: {technique_id} - artifacts may remain{item_tag}"
            }}
'''

        script += f'''        }}
        "^[Ss]" {{
            Write-LogEvent -Level "SKIP" -Message "Test {idx} skipped by user: {technique_id}{item_tag}"
            $global:Results["{func_name}"] = "SKIPPED"
        }}
        default {{
            Write-LogEvent -Level "SKIP" -Message "Test {idx} skipped: {technique_id}{item_tag}"
            $global:Results["{func_name}"] = "SKIPPED"
        }}
    }}
    Write-Host ""
}}

'''

    # Add menu function
    script += '''
function Show-Menu {
    Clear-Host
    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host "|           PTVault Test Plan Execution Menu               |" -ForegroundColor Cyan
    Write-Host "+==============================================================+" -ForegroundColor Cyan
'''

    script += f'    Write-Host "|  Plan: {plan.get("name", "Unnamed")[:50]:<52} |" -ForegroundColor Cyan\n'
    script += '''    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host ""
'''

    for idx, item in enumerate(compatible_items, 1):
        raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
        raw_technique = item.get('technique_id') or 'Custom'
        test_name = _powershell_escape_dquoted(raw_name)
        technique_id = _powershell_escape_dquoted(raw_technique)
        # Machine-readable tag so PTVault can map log lines back to plan items
        item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
        display_name = _powershell_escape_dquoted(f"{raw_technique}: {raw_name}"[:55])
        script += f'    Write-Host "  [{idx}] {display_name}" -ForegroundColor White\n'

    script += f'''    Write-Host ""
    Write-Host "  [A] Run ALL tests" -ForegroundColor Green
    Write-Host "  [R] Show results summary" -ForegroundColor Yellow
    Write-Host "  [B] Back to mode selection" -ForegroundColor Cyan
    Write-Host "  [Q] Quit" -ForegroundColor Red
    Write-Host ""
    Write-Host "+==============================================================+" -ForegroundColor Cyan
}}

function Show-Results {{
    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "                           RESULTS SUMMARY" -ForegroundColor Blue
    Write-Host "                    Generated: $(Get-Timestamp)" -ForegroundColor Magenta
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host ""

    $passed = 0
    $failed = 0
    $skipped = 0
'''

    for idx, item in enumerate(compatible_items, 1):
        func_name = f"Test-{idx}"
        raw_name = item.get('custom_name') or item.get('atomic_test_name') or f"Test {idx}"
        raw_technique = item.get('technique_id') or 'Custom'
        test_name = _powershell_escape_dquoted(raw_name)
        technique_id = _powershell_escape_dquoted(raw_technique)
        # Machine-readable tag so PTVault can map log lines back to plan items
        item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
        script += f'''
    $result = $global:Results["{func_name}"]
    if (-not $result) {{ $result = "NOT RUN" }}
    switch ($result) {{
        "PASSED" {{ Write-Host "  [PASS] [{idx}] {technique_id}: {test_name}" -ForegroundColor Green; $passed++ }}
        "FAILED" {{ Write-Host "  [FAIL] [{idx}] {technique_id}: {test_name}" -ForegroundColor Red; $failed++ }}
        "SKIPPED" {{ Write-Host "  [SKIP] [{idx}] {technique_id}: {test_name}" -ForegroundColor Yellow; $skipped++ }}
        default {{ Write-Host "  [----] [{idx}] {technique_id}: {test_name}" -ForegroundColor Cyan }}
    }}
'''

    script += f'''
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Total: {len(compatible_items)} | Passed: $passed | Failed: $failed | Skipped: $skipped"
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
{_powershell_cleanup_summary(compatible_items)}    Read-Host "Press Enter to continue"
}}

function Run-AllTests {{
    Write-LogEvent -Level "START" -Message "Beginning batch execution of all {len(compatible_items)} tests"
    Write-Host ""
    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host "|        BATCH EXECUTION - {len(compatible_items)} TESTS                         |" -ForegroundColor Yellow
    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host ""
    $batchStart = Get-Date
'''

    for idx in range(1, len(compatible_items) + 1):
        script += f"    Test-{idx}\n"

    script += '''    $batchEnd = Get-Date
    $batchDuration = ($batchEnd - $batchStart).TotalSeconds
    Write-Host ""
    Write-LogEvent -Level "END" -Message "Batch execution completed (total duration: $([math]::Round($batchDuration,1))s)"
    Show-Results
}

# Run tests sequentially with prompts
function Run-Sequential {
'''
    script += f'    Write-LogEvent -Level "START" -Message "Beginning sequential execution of {len(compatible_items)} tests"\n    Write-Host ""\n'

    for idx in range(1, len(compatible_items) + 1):
        script += f"    Test-{idx}\n"

    script += '''    Write-Host ""
    Write-LogEvent -Level "END" -Message "Sequential execution completed"
    Show-Results
}

# Run every test without per-test prompts (gated by Confirm-Automatic)
function Run-Automatic {
'''
    script += f'''    Write-LogEvent -Level "START" -Message "Beginning automatic execution of all {len(compatible_items)} tests"
    Write-Host ""
    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host "|     AUTOMATIC EXECUTION MODE - {len(compatible_items)} TESTS" -ForegroundColor Yellow
    Write-Host "|     Default inputs, cleanup after each test" -ForegroundColor Blue
    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host ""
    $batchStart = Get-Date
'''

    for idx, item in enumerate(compatible_items, 1):
        script += _powershell_automatic_test(idx, len(compatible_items), item)

    script += '''
    $batchEnd = Get-Date
    $batchDuration = ($batchEnd - $batchStart).TotalSeconds
    Write-Host ""
    Write-LogEvent -Level "END" -Message "Automatic execution completed (total duration: $([math]::Round($batchDuration,1))s)"
    Show-Results
}

# Execution mode selection
function Select-ExecutionMode {
    Clear-Host
    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host "|           PTVault Test Plan Execution                      |" -ForegroundColor Blue
    Write-Host "+==============================================================+" -ForegroundColor Cyan
'''

    script += f'    Write-Host "|  Plan: {plan.get("name", "Unnamed")[:50]:<52} |" -ForegroundColor Cyan\n'
    script += f'    Write-Host "|  Tests: {len(compatible_items):<53} |" -ForegroundColor Cyan\n'

    script += '''    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host "|                                                              |" -ForegroundColor Cyan
    Write-Host "|  " -ForegroundColor Cyan -NoNewline; Write-Host "How would you like to run the tests?" -ForegroundColor Yellow -NoNewline; Write-Host "                       |" -ForegroundColor Cyan
    Write-Host "|                                                              |" -ForegroundColor Cyan
    Write-Host "|  " -ForegroundColor Cyan -NoNewline; Write-Host "[1]" -ForegroundColor Green -NoNewline; Write-Host " Run ALL tests automatically                            |" -ForegroundColor Cyan
    Write-Host "|      Execute all tests sequentially without stopping         |" -ForegroundColor Cyan
    Write-Host "|                                                              |" -ForegroundColor Cyan
    Write-Host "|  " -ForegroundColor Cyan -NoNewline; Write-Host "[2]" -ForegroundColor Blue -NoNewline; Write-Host " Run tests ONE AT A TIME                                |" -ForegroundColor Cyan
    Write-Host "|      Prompt before each test execution                       |" -ForegroundColor Cyan
    Write-Host "|                                                              |" -ForegroundColor Cyan
    Write-Host "|  " -ForegroundColor Cyan -NoNewline; Write-Host "[3]" -ForegroundColor Yellow -NoNewline; Write-Host " Interactive menu                                       |" -ForegroundColor Cyan
    Write-Host "|      Choose which tests to run from a menu                   |" -ForegroundColor Cyan
    Write-Host "|                                                              |" -ForegroundColor Cyan
    Write-Host "|  " -ForegroundColor Cyan -NoNewline; Write-Host "[Q]" -ForegroundColor Red -NoNewline; Write-Host " Quit                                                   |" -ForegroundColor Cyan
    Write-Host "|                                                              |" -ForegroundColor Cyan
    Write-Host "+==============================================================+" -ForegroundColor Cyan
    Write-Host ""
    $mode = Read-Host "Select execution mode [1/2/3/Q]"
    switch -Regex ($mode) {
        "^1$" { if (Confirm-Automatic) { Run-Automatic } else { Select-ExecutionMode } }
        "^2$" { Run-Sequential }
        "^3$" { Interactive-Menu }
        "^[Qq]$" { Write-Host "Goodbye!"; return }
        default {
            Write-Host "Invalid option" -ForegroundColor Red
            Start-Sleep -Seconds 1
            Select-ExecutionMode
        }
    }
}

# Interactive menu loop
function Interactive-Menu {
    while ($true) {
        Show-Menu
        $choice = Read-Host "Select option"
        switch -Regex ($choice) {
'''

    for idx in range(1, len(compatible_items) + 1):
        script += f'            "^{idx}$" {{ Test-{idx}; Read-Host "Press Enter to continue" }}\n'

    script += '''            "^[Aa]$" { Run-AllTests }
            "^[Rr]$" { Show-Results }
            "^[Bb]$" { Select-ExecutionMode; return }
            "^[Qq]$" { Write-Host "Goodbye!"; return }
            default { Write-Host "Invalid option" -ForegroundColor Red; Start-Sleep -Seconds 1 }
        }
    }
}

# Confirm this host is in scope, then choose how to run
Confirm-Authorization
Select-ExecutionMode
'''

    return script


def get_script_filename(plan_name, platform):
    """Generate a safe filename for the script."""
    import re
    # Sanitize plan name
    safe_name = re.sub(r'[^\w\s-]', '', plan_name)
    safe_name = re.sub(r'[-\s]+', '_', safe_name).strip('_')
    if not safe_name:
        safe_name = 'test_plan'

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if platform == 'powershell':
        return f"{safe_name}_{timestamp}.ps1"
    else:
        return f"{safe_name}_{timestamp}.sh"


def generate_readme(plan, items, platform='bash'):
    """
    Generate a README file with instructions for running the script.

    Args:
        plan: Test plan dict with name, description
        items: List of test plan items with atomic details
        platform: 'bash' or 'powershell'

    Returns:
        str: README content in Markdown format
    """
    import re

    plan_name = plan.get('name', 'Unnamed Test Plan')
    plan_desc = plan.get('description', '')
    script_filename = get_script_filename(plan_name, platform)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Count tests by platform
    linux_count = 0
    windows_count = 0
    for item in items:
        platforms = []
        if item.get('supported_platforms'):
            if isinstance(item['supported_platforms'], str):
                try:
                    import json
                    platforms = json.loads(item['supported_platforms'])
                except (json.JSONDecodeError, ValueError):
                    platforms = []
            else:
                platforms = item['supported_platforms']

        if not platforms:
            linux_count += 1
            windows_count += 1
        else:
            if 'linux' in platforms or 'macos' in platforms:
                linux_count += 1
            if 'windows' in platforms:
                windows_count += 1

    test_count = linux_count if platform == 'bash' else windows_count

    readme = f"""# {plan_name} - Test Execution Guide

**Generated:** {timestamp}
**Platform:** {'Bash (Linux/macOS)' if platform == 'bash' else 'PowerShell (Windows)'}
**Script File:** `{script_filename}`
**Total Tests:** {test_count}

---

## Overview

{plan_desc if plan_desc else 'This test plan contains automated security tests generated from PTVault.'}

---

## Prerequisites

"""

    if platform == 'bash':
        readme += """### Linux/macOS Requirements

- **Bash 4.0+** (for associative arrays support)
- **Root/sudo access** may be required for some tests
- **Standard Unix utilities:** date, grep, awk, etc.

### Verify Bash Version

```bash
bash --version
# Should show version 4.0 or higher
```

"""
    else:
        readme += """### Windows Requirements

- **PowerShell 5.1+** (Windows 10/11 or Server 2016+)
- **Administrator privileges** may be required for some tests
- **Execution policy** must allow script execution

### Check PowerShell Version

```powershell
$PSVersionTable.PSVersion
# Should show version 5.1 or higher
```

### Set Execution Policy (if needed)

```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

"""

    readme += """---

## Running the Script

"""

    if platform == 'bash':
        readme += f"""### Quick Start

```bash
# 1. Make the script executable
chmod +x {script_filename}

# 2. Run the script
./{script_filename}

# Or run with bash directly
bash {script_filename}
```

### Execution Modes

When you run the script, you'll be presented with three execution modes:

| Mode | Description |
|------|-------------|
| **[1] Run ALL automatically** | Executes all tests sequentially without prompts. Best for automated testing. |
| **[2] Run ONE AT A TIME** | Prompts before each test. Recommended for first-time execution. |
| **[3] Interactive menu** | Select individual tests to run from a menu. Best for targeted testing. |

### Command Line Examples

```bash
# Run with verbose output
bash -x {script_filename}

# Run and save output to file
./{script_filename} 2>&1 | tee test_results.log

# Run in background (not recommended - interactive)
# nohup ./{script_filename} > output.log 2>&1 &
```

"""
    else:
        readme += f"""### Quick Start

```powershell
# 1. Navigate to script directory
cd C:\\path\\to\\scripts

# 2. Run the script
.\\{script_filename}

# Or with full path
powershell -ExecutionPolicy Bypass -File ".\\{script_filename}"
```

### Execution Modes

When you run the script, you'll be presented with three execution modes:

| Mode | Description |
|------|-------------|
| **[1] Run ALL automatically** | Executes all tests sequentially without prompts. Best for automated testing. |
| **[2] Run ONE AT A TIME** | Prompts before each test. Recommended for first-time execution. |
| **[3] Interactive menu** | Select individual tests to run from a menu. Best for targeted testing. |

### Command Line Examples

```powershell
# Run with bypass execution policy
powershell -ExecutionPolicy Bypass -File ".\\{script_filename}"

# Run and save output to file
.\\{script_filename} | Tee-Object -FilePath test_results.log

# Run with verbose output
powershell -ExecutionPolicy Bypass -File ".\\{script_filename}" -Verbose
```

"""

    readme += """---

## Understanding the Output

### Log Format

The script produces timestamped, color-coded output for easy log correlation:

```
[2024-01-15 10:30:45] [START] Executing test 1: T1059.001 - PowerShell Command
[2024-01-15 10:30:46] [PASS] Test 1 completed successfully (exit code: 0, duration: 1s)
[2024-01-15 10:30:46] [END] Finished test 1: T1059.001
```

### Log Levels

| Level | Color | Description |
|-------|-------|-------------|
| `[START]` | Green | Test execution beginning |
| `[END]` | Blue | Test execution completed |
| `[PASS]` | Green | Test passed (exit code 0) |
| `[FAIL]` | Red | Test failed (non-zero exit) |
| `[SKIP]` | Yellow | Test skipped by user |
| `[INFO]` | Cyan | Informational message |
| `[EXEC]` | Yellow | Command being executed |

### Results Summary

At the end of execution, a summary is displayed:

```
==================================================
                    RESULTS SUMMARY
==================================================

Test 1 (T1059.001): PASSED
Test 2 (T1055.001): FAILED
Test 3 (T1003.001): SKIPPED

==================================================
Total: 3 | Passed: 1 | Failed: 1 | Skipped: 1
==================================================
```

---

## Saving Output for Evidence

### Capture Full Session

"""

    if platform == 'bash':
        readme += f"""```bash
# Using script command (captures everything)
script -c "./{script_filename}" test_session.log

# Using tee (captures stdout/stderr)
./{script_filename} 2>&1 | tee test_output.log

# With timestamp in filename
./{script_filename} 2>&1 | tee "test_$(date +%Y%m%d_%H%M%S).log"
```

"""
    else:
        readme += f"""```powershell
# Using Start-Transcript (captures everything)
Start-Transcript -Path "test_session.log"
.\\{script_filename}
Stop-Transcript

# Using Tee-Object
.\\{script_filename} | Tee-Object -FilePath "test_output.log"

# With timestamp in filename
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
.\\{script_filename} | Tee-Object -FilePath "test_$timestamp.log"
```

"""

    readme += """## Safety Checks

Before anything runs, the script shows this host's name, addresses, user
and privilege level, and asks you to type the hostname to confirm the
machine is in scope. For unattended runs set `PTVAULT_AUTHORIZED_HOST` to
the machine's hostname instead; a mismatch stops the script.

- **Automatic mode** asks you to type `RUN ALL`. It uses each input's
  default value, skips tests whose required inputs have no default, skips
  tests that need root/Administrator when the session isn't elevated, and
  runs cleanup after every test.
- **Per-test runs** warn when a test needs elevation, and the cleanup
  prompt defaults to yes.
- The results summary lists every test whose cleanup did not run, since
  its artifacts may still be on the system. Cleanup outcomes are also in
  the session log.

### Import Results into PTVault

Bring the captured log back into PTVault to fill in each test's status,
output and timestamps: **Test Plans → Executions → Import log**, then pick
the host the script ran on. Log lines carry an `[item=N]` tag so results map
to the right tests, including runs of a plan copied from a template.
Detection outcomes (prevented / alerted / logged / not detected) are not in
the log; record those from the blue team's side.

---

## Test List

The following tests are included in this script:

| # | Technique ID | Test Name |
|---|--------------|-----------|
"""

    # List all tests
    for idx, item in enumerate(items, 1):
        technique_id = item.get('technique_id', 'Custom')
        # Machine-readable tag so PTVault can map log lines back to plan items
        item_tag = f" [item={item['id']}]" if item.get('id') is not None else ''
        test_name = item.get('custom_name') or item.get('atomic_test_name') or f'Test {idx}'
        # Escape pipe characters in test name for markdown table
        test_name = test_name.replace('|', '\\|')
        readme += f"| {idx} | {technique_id} | {test_name} |\n"

    readme += """

---

## Safety Warnings

⚠️ **IMPORTANT: Read before executing**

1. **Authorization Required**: Only run these tests on systems you are authorized to test.

2. **System Modifications**: Some tests may modify system state, create files, or change configurations.

3. **Cleanup Commands**: Many tests include cleanup commands that run after execution. Review these before running.

4. **Test Environment**: It is recommended to run tests in an isolated test environment first.

5. **Monitoring**: Ensure security monitoring is in place to detect test activities.

6. **Documentation**: Keep records of all test executions for compliance and audit purposes.

---

## Troubleshooting

### Common Issues

"""

    if platform == 'bash':
        readme += """| Issue | Solution |
|-------|----------|
| `Permission denied` | Run `chmod +x script.sh` or use `bash script.sh` |
| `bash: syntax error` | Ensure Bash 4.0+ is installed |
| `Command not found` | Install required tools or check PATH |
| Script hangs | Some tests require user input; check prompts |

"""
    else:
        readme += """| Issue | Solution |
|-------|----------|
| `cannot be loaded because running scripts is disabled` | Set execution policy: `Set-ExecutionPolicy Bypass` |
| `Access is denied` | Run PowerShell as Administrator |
| `cmdlet not found` | Check PowerShell version and installed modules |
| Script hangs | Some tests require user input; check prompts |

"""

    readme += """---

## Support

This script was generated by **PTVault** - Penetration Testing Evidence Manager.

For issues or questions:
- Review the test commands before execution
- Check PTVault documentation for test plan management
- Ensure all prerequisites are met

---

*Generated by PTVault Test Plan Script Generator*
"""

    return readme


def get_readme_filename(plan_name):
    """Generate a filename for the README."""
    import re
    # Sanitize plan name
    safe_name = re.sub(r'[^\w\s-]', '', plan_name)
    safe_name = re.sub(r'[-\s]+', '_', safe_name).strip('_')
    if not safe_name:
        safe_name = 'test_plan'

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{safe_name}_{timestamp}_README.md"

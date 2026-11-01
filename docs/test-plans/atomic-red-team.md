# Atomic Red Team

Atomic Red Team is an open-source library of small, focused tests — called "atomics" — mapped to MITRE ATT&CK techniques. PTVault downloads and indexes this library locally for offline use.

## Setting Up the Atomics Library

### Downloading the Library

The Atomic Red Team library must be downloaded before use. This is a one-time operation.

1. Click the **Test Plans** tab
2. Click **Atomic Red Team**
3. Click **Download Atomics**
4. Wait for the download to complete — progress is shown on screen
5. When finished, the library status shows the total technique and test counts

The library is stored locally in `data/atomics/` and does not require an internet connection after download.

### Updating the Library

To update to the latest Atomic Red Team version:

1. Click **Download Atomics** again
2. PTVault fetches the latest version from GitHub and replaces the local copy

### Library Status

The status panel shows:
- **Installed**: Whether the library is downloaded
- **Version**: Date/commit of the downloaded library
- **Techniques**: Total number of MITRE techniques covered
- **Tests**: Total number of executable atomic tests
- **Last Updated**: When the library was last downloaded

## Browsing Atomics

After downloading, atomics are accessible in the library browser.

### Browsing by Tactic

Click a tactic in the sidebar to see all techniques under that tactic:
- Reconnaissance
- Resource Development
- Initial Access
- Execution
- Persistence
- Privilege Escalation
- Defense Evasion
- Credential Access
- Discovery
- Lateral Movement
- Collection
- Command and Control
- Exfiltration
- Impact

### Searching the Library

Use the search bar to find atomics by:
- **Technique ID**: `T1059.001`
- **Technique name**: `PowerShell`
- **Description keywords**: `LSASS`, `kerberoast`, `mimikatz`

### Atomic Test Details

Click any technique to see all atomic tests for that technique. Each test shows:

| Field | Description |
|-------|-------------|
| Test Name | Short descriptive name |
| Test Number | Index within the technique (e.g., Test #1) |
| Description | What the test does and what it simulates |
| Supported Platforms | Windows, Linux, macOS |
| Executor | How the test runs: `bash`, `cmd`, `powershell`, `sh`, `manual` |
| Elevation Required | Whether admin/root access is needed |
| Prerequisites | What must be set up before running |
| Input Arguments | Configurable parameters (defaults provided) |
| Execution Command | The actual command to run |
| Cleanup Command | Commands to undo the test's changes |

## Adding Tests to a Test Plan

1. Find the atomic test you want to include
2. Click **Add to Test Plan**
3. Select the target test plan (or create a new one)
4. Optionally customize input argument values
5. Click **Add**

## Creating a Test Plan

1. Click **+ New Test Plan**
2. Enter a name (e.g., `Active Directory Assessment`, `External Web Testing`)
3. Add atomic tests using the library browser
4. Add custom test items for non-atomic tests

Test plans are reusable templates — the same plan can be applied to multiple engagements.

## Script Generation

PTVault can generate executable scripts from a test plan:

1. Open a test plan
2. Click **Generate Script**
3. Choose format: **Bash** or **PowerShell**
4. Download the generated script file

The script contains all enabled test commands with their input argument values substituted, organized by technique.

> **Warning:** Always review generated scripts before execution on target systems. Ensure you have explicit authorization for all tests included in the script.

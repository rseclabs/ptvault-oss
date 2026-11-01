# Test Plans

The Test Plans section provides structured penetration testing workflows integrated with the MITRE ATT&CK framework and Atomic Red Team library.

## In This Section

- [MITRE ATT&CK Navigator](./mitre-attack.md) — Import and visualize ATT&CK layers
- [Atomic Red Team](./atomic-red-team.md) — Browse, search, and track atomic tests
- [Execution Tracking](./execution-tracking.md) — Track test execution status per engagement

## Overview

The Test Plans section helps you:

1. **Plan**: Import a MITRE ATT&CK Navigator layer to define which techniques you will test
2. **Execute**: Use the Atomic Red Team library to find executable tests for each technique
3. **Track**: Record execution status, output, and evidence for each test

## Why Use Structured Test Plans?

- Ensure complete coverage of the agreed attack surface
- Demonstrate methodology to clients and auditors
- Reuse test plans across similar engagements
- Automatically generate test scripts (Bash and PowerShell)
- Link test execution records to collected evidence

## Workflow

```
Import Navigator Layer → Browse Atomics → Create Test Plan → Execute Tests → Record Results → Link Evidence
```

## See Also

- [Reporting](../reporting/README.md) — Document findings from test execution
- [Evidence](../evidence/README.md) — Link evidence to execution records

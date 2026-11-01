# PTVault Documentation

> **Penetration Testing Evidence Manager** — A secure, local-first workspace for cybersecurity professionals.

PTVault consolidates your entire penetration testing workflow into a single encrypted application: manage engagements, collect and organize evidence, track hosts and vulnerabilities, plan and execute tests, and generate professional client reports — all without any cloud dependencies.

---

## Table of Contents

### Getting Started
- [Getting Started Guide](./getting-started/README.md)
  - [Installation](./getting-started/installation.md)
  - [First-Time Setup](./getting-started/first-time-setup.md)
  - [Quick Start Workflow](./getting-started/quick-start.md)

### Authentication & Access
- [Authentication Overview](./authentication/README.md)
  - [Login & Logout](./authentication/login-logout.md)
  - [Session Management](./authentication/session-management.md)
  - [Roles & Permissions](./authentication/roles-permissions.md)

### Core Features

- [Dashboard](./dashboard/README.md) — Per-engagement metrics and charts

- [Engagements](./engagements/README.md) — Manage client penetration testing projects
  - [Creating Engagements](./engagements/creating-engagements.md)
  - [Managing Engagements](./engagements/managing-engagements.md)
  - [Exporting & Importing](./engagements/exporting-importing.md)

- [Hosts](./hosts/README.md) — Track target systems and findings
  - [Adding & Managing Hosts](./hosts/adding-hosts.md)
  - [Host Indicators & Colors](./hosts/host-indicators.md)
  - [Ports & Credentials](./hosts/ports-credentials.md)
  - [Host Notes](./hosts/host-notes.md)

- [Evidence](./evidence/README.md) — Collect and organize findings
  - [Collecting Evidence](./evidence/collecting-evidence.md)
  - [File Uploads & Tool Imports](./evidence/file-uploads.md)
  - [Searching & Filtering](./evidence/searching-filtering.md)
  - [Bulk Operations](./evidence/bulk-operations.md)

- [Port Grid](./port-grid/README.md) — Visual network port matrix

- [Tool Parsers](./tool-parsers/README.md) — Auto-import security tool output
  - [Nmap](./tool-parsers/nmap.md)
  - [Burp Suite](./tool-parsers/burp-suite.md)
  - [Nessus](./tool-parsers/nessus.md)
  - [Other Supported Tools](./tool-parsers/other-tools.md)

### Reporting, Test Plans & Collaboration

- [Reporting](./reporting/README.md) — Build professional reports
  - [Writeups Database](./reporting/writeups-database.md)
  - [Report Builder](./reporting/report-builder.md)
  - [Format Tools Reference](./reporting/format-tools.md)
  - [Exporting Reports](./reporting/exporting-reports.md)

- [Test Plans](./test-plans/README.md) — Structured testing with MITRE ATT&CK
  - [MITRE ATT&CK Navigator](./test-plans/mitre-attack.md)
  - [Atomic Red Team](./test-plans/atomic-red-team.md)
  - [Execution Tracking](./test-plans/execution-tracking.md)

- [Relationships](./relationships/README.md) — Model attack chains and dependencies

### Built-In Tools

- [Tools Overview](./tools/README.md)
  - [CyberChef](./tools/cyberchef.md) — Data transformation toolkit
  - [MSFVenom Builder](./tools/msfvenom-builder.md) — Payload generator
  - [Command Hub](./tools/command-hub.md) — Command reference & shells
  - [Calculators](./tools/calculators.md) — CVSS 3.1 & Subnet calculator
  - [Decoders](./tools/decoders.md) — JWT decoder & PowerShell encoder
  - [Attack Maps](./tools/attack-maps.md) — Visual attack path diagrams

### Administration

- [Admin Guide](./admin/README.md)
  - [User Management](./admin/user-management.md)
  - [Team Management](./admin/team-management.md)
  - [Engagement Management (Admin)](./admin/engagements.md)
  - [Client Management](./admin/clients.md)
  - [Database Encryption](./admin/database-encryption.md)
  - [Session Settings](./admin/session-settings.md)

### Reference

- [Security Architecture](./security/README.md)

---

## Quick Navigation

| I want to… | Go to… |
|---|---|
| Set up PTVault for the first time | [First-Time Setup](./getting-started/first-time-setup.md) |
| Start a new client project | [Creating Engagements](./engagements/creating-engagements.md) |
| Add hosts from an Nmap scan | [Nmap Parser](./tool-parsers/nmap.md) |
| Track compromised hosts | [Host Indicators](./hosts/host-indicators.md) |
| Build a client report | [Report Builder](./reporting/report-builder.md) |
| Manage users and teams | [User Management](./admin/user-management.md) |
| Enable database encryption | [Database Encryption](./admin/database-encryption.md) |

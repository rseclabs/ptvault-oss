# Hosts

The **Hosts** section is the primary workspace for organizing your penetration testing findings. Each host represents a target system, and hosts contain ports, credentials, notes, and linked evidence.

## In This Section

- [Adding & Managing Hosts](./adding-hosts.md) — Create, search, and delete hosts
- [Host Indicators & Colors](./host-indicators.md) — Track host status visually
- [Ports & Credentials](./ports-credentials.md) — Document open ports and discovered credentials
- [Host Notes](./host-notes.md) — Per-host Markdown notes

## Layout

The Hosts section uses a two-panel layout:

- **Left panel (Host List)**: All hosts for the active engagement, plus a special "General" entry
- **Right panel (Host Detail)**: Tabs for Indicators, Notes, Open Ports, Findings, and Credentials

## The General Section

The **General** entry at the top of the host list is a special pseudo-host for engagement-level data not tied to a specific system. It has its own tabs:
- **Notes**: Engagement-wide observations
- **Credentials**: Credentials not tied to a specific host
- **Terminal Dumps**: Raw command output
- **Findings**: Vulnerabilities without a specific target host

## Host Search

The search bar above the host list performs real-time search across:
- IP addresses and hostnames
- Host notes
- Evidence titles and content
- Port numbers and service names
- Credential usernames
- Nested tool scan data (e.g., Nessus vulnerability descriptions)

## Quick Reference

| Task | How |
|------|-----|
| Add a host | Click **+ Add Host** |
| Import hosts from Nmap | [Import tool output](../tool-parsers/nmap.md) |
| Mark a host as compromised | [Set indicators](./host-indicators.md) |
| Add a discovered port | [Ports tab](./ports-credentials.md) |
| Record a credential | [Credentials tab](./ports-credentials.md) |
| View the full network | [Port Grid](../port-grid/README.md) |

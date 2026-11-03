# PTVault - Penetration Testing Evidence Manager

  What is PTVault?

  PTVault is a secure, all-in-one workspace for cybersecurity professionals who conduct penetration testing—essentially "ethical hacking" engagements where security experts attempt to break into systems to find vulnerabilities before malicious
  actors do.

  Think of PTVault as the professional's toolkit and filing cabinet combined. It's where penetration testers organize their work, collect evidence, track their findings, and produce the professional reports that clients need to understand and fix
  their security issues.

  The Problem PTVault Solves

  Penetration testers today face a fragmented workflow:
  - Evidence scattered across folders, screenshots, and notes
  - Sensitive client data stored in various cloud tools with unknown security
  - Hours spent manually formatting reports
  - No systematic way to reuse knowledge from previous engagements
  - Difficulty tracking which systems have been tested and what was found

  PTVault consolidates all of this into a single, encrypted application that runs entirely on the tester's own computer—no cloud dependencies, no data leaving their control.

### Key Capabilities

#### Engagement Management
  Testers can manage multiple client projects simultaneously, each with its own scope, timeline, and findings—all organized and searchable.

#### Evidence Collection
  Screenshots, command outputs, tool results, and notes are all stored in one place with tagging and full-text search. When a tester needs to find "that screenshot from Tuesday showing the SQL injection," they can find it in seconds.

#### Target Tracking
  A visual dashboard shows all target systems, which ports are open, what credentials have been discovered, and the current status of each system (compromised, interesting, out of scope, etc.).

#### Tool Integration
  PTVault automatically imports and parses results from industry-standard tools like Nmap, Nessus, Burp Suite, OWASP ZAP, Nuclei and BloodHound—eliminating manual data entry.
### Professional Report Generation
  A drag-and-drop report builder lets testers create polished, client-ready reports in minutes rather than hours. Reports can be exported to HTML, PDF, Word, or Markdown.
### Built-in Utilities
  Common tools are built right in: payload generators, encoding/decoding utilities, a command reference library, and integration with the MITRE ATT&CK framework for systematic testing.
#### Security-First Design

  The database is encrypted at rest with SQLCipher (AES-256), using a key derived from your password with Argon2id. Client data never touches the cloud. The application works offline, making it suitable even for highly secure, air-gapped environments.

  Target Market

  - Professional penetration testing firms managing multiple client engagements
  - Enterprise security teams conducting internal assessments
  - Compliance auditors who need organized evidence for regulatory requirements
  - Independent security consultants who need professional-grade tools without enterprise pricing

#### Value Proposition

  PTVault transforms a chaotic, manual process into a streamlined professional workflow. Testers spend less time on administration and more time on actual security testing. Reports that once took a full day to compile can be generated in under an hour. And clients benefit from more thorough, better-documented assessments.

  In simple terms: PTVault makes penetration testers more productive while keeping their clients' sensitive data completely
  secure.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Getting Started](#getting-started)
- [User Guide](#user-guide)
  - [Engagements](#engagements)
  - [Evidence Management](#evidence-management)
  - [Port Grid](#port-grid)
  - [Tools](#tools)
  - [Reporting](#reporting)
  - [Test Plans](#test-plans)
- [Report Generation](#report-generation)
  - [Format Tools Reference](#format-tools-reference)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Security](#security)

---

## Overview

PTVault is designed for penetration testers and security professionals who need a centralized, secure platform to:

- Manage multiple client engagements
- Collect and organize evidence (notes, screenshots, command output)
- Track hosts, ports, and credentials discovered during testing
- Document vulnerabilities with severity ratings and remediation guidance
- Generate professional reports with customizable formatting
- Plan and track test execution using MITRE ATT&CK and Atomic Red Team

All data is stored locally in an encrypted SQLite database, ensuring your sensitive client data never leaves your control.


---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Multi-Engagement Support** | Manage multiple penetration testing projects simultaneously |
| **Host Management** | Track target systems with status indicators and color coding |
| **Evidence Collection** | Store notes, screenshots, command output, and tool results |
| **Vulnerability Tracking** | Document findings with CVSS scoring and remediation |
| **Report Generation** | Build professional reports with drag-and-drop formatting |
| **Tool Integration** | Import results from 11 tools, including Nmap, Nessus, Burp Suite and BloodHound |
| **Test Planning** | MITRE ATT&CK Navigator and Atomic Red Team integration |

### Security Features

- Multi-user accounts (admin / editor / viewer) with Argon2id password hashing
- Session-based authentication with JWT tokens
- Local SQLite database (no cloud dependencies)
- Per-engagement data isolation
- Offline-capable for air-gapped environments

---

## Installation

### Requirements

- Python 3.10+
- Linux (Kali/Parrot work well), macOS or Windows
- Optional: the Pango library for server-side PDF export (`sudo apt install libpango-1.0-0 libpangoft2-1.0-0` or `brew install pango`). Without it, PDF export uses the browser's print dialog.

Database encryption needs no extra setup: the `sqlcipher3` package in `requirements.txt` ships with SQLCipher built in.

### Option 1: Python

```bash
git clone https://github.com/rseclabs/ptvault-oss.git
cd ptvault-oss
python3 -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

PTVault is now running at http://localhost:5001. It only listens on localhost; use `python app.py -i 0.0.0.0 -p 5001` to allow other machines, ideally behind HTTPS (see [DEPLOYMENT.md](DEPLOYMENT.md)).

### Option 2: Docker

```bash
git clone https://github.com/rseclabs/ptvault-oss.git
cd ptvault-oss
cp .env.example .env
docker compose up -d
```

PTVault is now running at http://localhost:5000, with the database and uploads stored in `./data`. On macOS, port 5000 may be taken by AirPlay Receiver; change the port mapping in `docker-compose.yml` (for example `"5050:5000"`) if so.

The container runs with `ENVIRONMENT=production`, so login cookies are marked Secure. Browsers accept them on `http://localhost`, but to reach the container from another machine put it behind HTTPS.

See [DEPLOYMENT.md](DEPLOYMENT.md) for PyInstaller builds, systemd and reverse-proxy setups.

### First-Time Setup

1. Open `http://localhost:5001` (Docker: `http://localhost:5000`). With no users yet, you are taken to the setup wizard.
2. Create the admin account: full name, email and a password of at least 8 characters. Your username is the part of the email before the `@` (for example `admin@example.com` gives `admin`). This step also encrypts the database.
3. Log in with that email (or username) and password.
4. Back up `data/encryption.key` and `data/encryption.salt` along with the database. The database cannot be opened without them.
5. Create your first engagement to begin.

---

## Getting Started

### Creating Your First Engagement

1. Click the **Engagements** tab
2. Click **+ New Engagement**
3. Fill in the engagement details:
   - **Name**: Project name (e.g., "ACME Corp External Pentest")
   - **Client Name**: Client organization name
   - **Short Name**: Abbreviated identifier (e.g., "ACME-EXT")
   - **Start/End Dates**: Engagement timeline
   - **Contact**: Client point of contact information
4. Click **Create**

### Adding Your First Host

1. Select your engagement from the sidebar
2. Go to the **Evidence** tab
3. Click **+ Add Host** in the left panel
4. Enter the IP address or hostname
5. The host will appear in your host list

---

## User Guide

### Engagements

The Engagements section provides an overview of all your penetration testing projects.
#### Engagement Properties

| Field | Description |
|-------|-------------|
| Name | Full project name |
| Client Name | Client organization |
| Short Name | Quick reference identifier |
| Description | Project scope and notes |
| Tags | Comma-separated labels for organization |
| Start Date | Engagement start date |
| End Date | Engagement end date |
| Status | Active, Completed, or Archived |
| Contact | Client POC (name, email, phone) |

#### Managing Engagements

- **Edit**: Click the edit icon on any engagement card
- **Delete**: Click the delete icon (requires confirmation)
- **Search**: Use the search bar to filter engagements
- **Switch**: Click any engagement card to make it active

---

### Evidence Management

The Evidence section is where you collect and organize all findings during a penetration test.

#### Host Management

Hosts are the primary organizational unit for evidence. Each host represents a target system.

**Adding Hosts:**
- Click **+ Add Host**
- Enter IP address or hostname
- Hosts are automatically created when importing tool output

**Host Indicators:**

| Indicator      | Icon | Description                              |     |
| -------------- | ---- | ---------------------------------------- | --- |
| Rooted         | `#`  | Full administrative/root access obtained |     |
| Shell          | `>_` | User-level shell access obtained         |     |
| Interested     | `★`  | Worth further investigation              |     |
| Not Interested | `✕`  | No valuable findings                     |     |
| Out of Scope   | `⛔`  | Do not test this host                    |     |
| Flagged        | `🚩` | Needs review or attention                |     |
| Reviewed       | `✓`  | Testing completed                        |     |

**Color Categories:**
Assign one of 10 colors to visually organize hosts (white, yellow, green, blue, red, purple, orange, teal, cyan, brown).

#### Host Sub-Sections

When a host is selected, the following tabs are available:

| Tab | Description |
|-----|-------------|
| **Indicators** | Set host status and color |
| **Notes** | Markdown notes specific to this host |
| **Open Ports** | Port, protocol, service, version, state |
| **Findings** | Vulnerabilities discovered on this host |
| **Credentials** | Usernames and passwords found |

#### General Section

The "General" entry in the host list provides engagement-wide storage:

- **Notes**: Engagement-level observations
- **Credentials**: Credentials not tied to a specific host
- **Terminal Dumps**: Raw command output capture
- **Findings**: Vulnerabilities not specific to one host
- 
#### Evidence Types

| Type | Use Case |
|------|----------|
| Note | Text observations and documentation |
| Screenshot | Visual evidence (images) |
| Command Output | Terminal/console results |
| Tool Output | Parsed results from security tools |
| Other | Miscellaneous evidence |

#### Importing Tool Output

PTVault can parse and import results from:

| Tool | Format | Imports |
|------|--------|---------|
| Nmap | XML | Hosts, ports, services |
| Nessus | `.nessus` XML | Vulnerabilities |
| Qualys | XML | Vulnerabilities |
| InsightVM / Nexpose | XML | Vulnerabilities |
| Burp Suite | XML | Web findings |
| OWASP ZAP | XML | Web findings |
| Acunetix | XML | Web findings |
| Nuclei | JSON | Findings |
| Metasploit | XML | Hosts, sessions, vulnerabilities |
| BloodHound | JSON | Active Directory objects and paths |
| CrackMapExec | JSON | Credentials and shares |

To import:
1. Click the **Import** button in the sidebar
2. Select the tool type
3. Choose your XML file
4. Review and confirm the import

---

### Port Grid

The Port Grid provides a visual matrix showing open and filtered ports across all hosts in the engagement.

#### Reading the Grid

- **Rows**: Individual hosts (IP addresses)
- **Columns**: Port numbers
- **Green cells**: Open ports
- **Orange cells**: Filtered ports
- **Empty cells**: Closed or not scanned

This view is useful for:
- Identifying common services across hosts
- Spotting unusual open ports
- Planning lateral movement paths

---

### Tools

The Tools section provides integrated security utilities.

#### Shells

Commonly used on liners to get a command shell in different languages.

#### MSFVenom Payload Builder

Generate Metasploit payloads without memorizing complex commands.

**Options:**
- **Platform**: Windows, Linux, macOS, Web, Android
- **Category**: Meterpreter, Shell, Exec, PHP, Java, Python
- **Format**: EXE, DLL, MSI, ELF, JAR, WAR, APK, ASP, etc.
- **Encoder**: Shikata Ga Nai, XOR, Alpha Mixed, etc.
- **Encryption**: XOR, AES-256, RC4, Base64
- **Bad Characters**: Characters to avoid in shellcode
- **Architecture**: x86, x64
- **LHOST/LPORT**: Callback address and port

#### Commands
A custom command database to keep all of your commonly used command in one searchable interface.

#### CVSS 3.1 Calculator

Calculate vulnerability severity scores using the Common Vulnerability Scoring System.

**Base Metrics:**
- Attack Vector (Network, Adjacent, Local, Physical)
- Attack Complexity (Low, High)
- Privileges Required (None, Low, High)
- User Interaction (None, Required)
- Scope (Unchanged, Changed)
- Confidentiality Impact (None, Low, High)
- Integrity Impact (None, Low, High)
- Availability Impact (None, Low, High)

#### CyberChef

Embedded data transformation tool for encoding, decoding, and analyzing data.

---


#### Subnet Calculator

A tool to quickly determine subnet information

#### JWT Decoder



#### Powershell Encoder

### Reporting

The Reporting section helps you document vulnerabilities and generate professional reports.

#### Writeups Database

Build a reusable library of vulnerability writeups.


**Writeup Types:**
- **Finding**: Technical vulnerability documentation
- **Narrative**: Executive summaries, methodology descriptions

**Finding Properties:**

| Field | Description |
|-------|-------------|
| Name | Vulnerability title |
| Category | Classification (e.g., Injection, XSS) |
| Criticality | Critical, High, Medium, Low |
| CVSS Score | Numeric severity (0.0-10.0) |
| Description | Technical details (supports Markdown) |
| Remediation | Fix recommendations (supports Markdown) |
| Tags | Keywords for searching |

**Narrative Properties:**
| Field | Description |
|-------|-------------|
| Name | Section title |
| Category | Document section type |
| Description | Content (supports Markdown) |
| Tags | Keywords for searching |

#### Report Generation

See the dedicated [Report Generation](#report-generation) section below.

---

### Test Plans

Plan and track penetration testing activities using industry frameworks.


#### MITRE ATT&CK Navigator

Import and visualize ATT&CK Navigator layers to plan your testing coverage.
**Features:**
- Import JSON layer files
- View technique coverage
- Track tested vs. untested techniques

#### Atomic Red Team

Access the Atomic Red Team library of executable tests.

**Setup:**
1. Click **Download Atomics** to fetch the library
2. Wait for the download to complete (progress shown)
3. Browse techniques by tactic or search

**Using Atomics:**
- View test details and prerequisites
- Copy commands for execution
- Track execution status per engagement
- Record output and link evidence



## Report Generation

The Report Generation feature allows you to build professional penetration testing reports using a drag-and-drop interface.

### Overview

The report generator has three panels:

| Panel | Purpose |
|-------|---------|
| **Available Items** (Left) | Source content to add to your report |
| **Workspace** (Center) | Your report structure - drag items here |
| **Live Preview** (Right) | Real-time preview of your report |

### Building a Report

1. **Create or Load a Report**
   - Enter a name in the report name field
   - Or select an existing report from the dropdown

2. **Add Content**
   - Drag items from the left panel to the workspace
   - Items can be reordered by dragging within the workspace

3. **Edit Content**
   - Click the edit (pencil) icon on any item to customize
   - Changes appear immediately in the preview

4. **Save and Export**
   - Click **Save** to preserve your work
   - Export as HTML, Markdown, PDF, or Word

### Source Content Types

#### Engagement Findings
Vulnerabilities documented during the current engagement. Each finding includes:
- Title and severity badge
- Description content
- Remediation recommendations
- CVSS score (if set)

#### Writeups Database
Reusable vulnerability templates from your writeups library.

#### Format Tools
Structural and visual elements to enhance your report.

---

## Format Tools Reference

PTVault includes 20 format tools organized into categories. Each tool can be customized after adding to your report.

### Basic Tools

#### Spacer
**Icon:** `↕` | **Editor:** None

Adds vertical whitespace between sections. Useful for visual separation.

---

#### Divider
**Icon:** `―` | **Editor:** None

Inserts a horizontal line to separate content sections.

---

#### Page Break
**Icon:** `↧` | **Editor:** None

Inserts a page break for printed/PDF output. Displayed as a dashed line indicator in the preview.

**Export:** Creates actual page break in PDF/print output

---

### Text Content Tools

#### Section Header
**Icon:** `H` | **Editor:** Yes

Creates a styled heading for report sections.

**Editor Options:**

| Option | Description |
|--------|-------------|
| Header Text | The heading content |
| Level | H1 (Title), H2 (Section), H3 (Subsection), H4 (Minor) |
| Numbered | Enable section numbering |
| Number | Manual section number (e.g., "1.1", "2.3.1") |

**Use Cases:**
- Report title (H1)
- Major sections like "Executive Summary" (H2)
- Subsections like "Critical Findings" (H3)
- Minor headings (H4)

---

#### Text Block
**Icon:** `¶` | **Editor:** Yes

Rich text paragraph with Markdown support.

**Supported Markdown:**
- `**bold**` for **bold text**
- `*italic*` for *italic text*
- `` `code` `` for `inline code`
- `[link text](url)` for hyperlinks
- Lists and other standard Markdown

**Use Cases:**
- Methodology descriptions
- Scope statements
- Custom narrative content

---

#### Quote Block
**Icon:** `❝` | **Editor:** Yes

Styled blockquote with optional attribution.

**Editor Options:**

| Option | Description |
|--------|-------------|
| Quote Text | The quoted content |
| Attribution | Source or speaker (optional) |

**Use Cases:**
- Client requirements or statements
- Excerpts from policies
- Important callouts from documentation

---

### List Tools

#### Bullet List
**Icon:** `•` | **Editor:** Yes

Unordered list with customizable items.

**Editor Features:**
- Add items with **+ Add Item** button
- Edit items inline
- Remove items with the X button
- Reorder by dragging

**Use Cases:**
- Feature lists
- Affected systems
- Recommendations without priority

---

#### Numbered List
**Icon:** `1.` | **Editor:** Yes

Ordered list with customizable items.

**Editor Features:**
- Add items with **+ Add Item** button
- Edit items inline
- Remove items with the X button
- Reorder by dragging

**Use Cases:**
- Step-by-step procedures
- Prioritized recommendations
- Attack chain documentation

---

#### Checklist
**Icon:** `☑` | **Editor:** Yes

Checkbox list with checked/unchecked states.

**Editor Options:**
| Option | Description |
|--------|-------------|
| Checklist Title | Header for the checklist |
| Items | Each with text and checkbox state |

**Use Cases:**
- Remediation tracking
- Compliance checklists
- Testing coverage verification

---

### Code & Terminal Tools

#### Code Block
**Icon:** `<>` | **Editor:** Yes

Syntax-highlighted code with language selection.

**Editor Options:**
| Option | Description |
|--------|-------------|
| Title | Optional filename or description |
| Language | Syntax highlighting language |
| Code | The code content |

**Supported Languages:**
Bash, Python, JavaScript, PowerShell, SQL, PHP, Java, C#, XML/HTML, JSON, YAML, Plain Text

**Use Cases:**
- Exploit code examples
- Configuration snippets
- Proof-of-concept scripts

---

#### Command Output
**Icon:** `$_` | **Editor:** Yes

Terminal-style display showing command and its output.

**Editor Options:**

| Option | Description |
|--------|-------------|
| Command | The command that was run |
| Output | The resulting output |

**Preview:** Dark terminal theme with green command line and white output text

**Use Cases:**
- Demonstrating successful exploits
- Showing enumeration results
- Documenting proof of access

---

### Callout & Highlight Tools

#### Alert Box
**Icon:** `⚠` | **Editor:** Yes

Colored callout box for important information.

**Alert Types:**

| Type | Color | Icon | Use Case |
|------|-------|------|----------|
| Info | Blue | ℹ | General information, tips |
| Warning | Yellow | ⚠ | Cautions, potential issues |
| Danger | Red | ⛔ | Critical warnings, security risks |
| Success | Green | ✓ | Positive outcomes, mitigations |

**Use Cases:**
- Highlighting critical risks
- Noting important caveats
- Calling out key recommendations

---

#### Key Finding
**Icon:** `★` | **Editor:** Yes

Highlighted summary box for critical discoveries.

**Editor Options:**

| Option | Description |
|--------|-------------|
| Title | Finding headline |
| Content | Brief description |

**Use Cases:**
- Executive summary highlights
- Most critical vulnerabilities
- Key risk indicators

---

#### Evidence Block
**Icon:** `◩` | **Editor:** Yes

Structured evidence documentation with image placeholder.

**Editor Options:**
| Option | Description |
|--------|-------------|
| Image Caption | Description of the screenshot/image |
| Description | Detailed explanation of the evidence |
| Impact | Business or technical impact statement |

**Use Cases:**
- Screenshot evidence with context
- Proof-of-concept documentation
- Visual evidence explanation

---

#### Image Placeholder
**Icon:** `▭` | **Editor:** Yes

Placeholder for images with caption.

**Editor Options:**

| Option | Description |
|--------|-------------|
| Caption | Figure caption (e.g., "Figure 1: Login Page") |
| Width | 100% (Full), 75% (Large), 50% (Medium), 25% (Small) |

**Use Cases:**
- Marking where screenshots will be inserted
- Placeholder during report drafting
- Figure references

---

### Data & Layout Tools

#### Table
**Icon:** `▦` | **Editor:** Yes

Customizable data table with headers and rows.

**Editor Features:**
- Add/remove columns
- Add/remove rows
- Edit header text
- Edit cell content

**Use Cases:**
- Vulnerability summary tables
- Host/port matrices
- Comparison data

---

#### Two-Column Layout
**Icon:** `▐▌` | **Editor:** Yes

Side-by-side content columns.

**Editor Options:**

| Option | Description |
|--------|-------------|
| Left Title | Left column heading |
| Left Content | Left column content (Markdown) |
| Right Title | Right column heading |
| Right Content | Right column content (Markdown) |

**Use Cases:**
- Before/After comparisons
- Current State vs. Recommendations
- Technical vs. Business impact

---

#### Timeline
**Icon:** `→` | **Editor:** Yes

Vertical timeline showing sequential events.

**Editor Features:**
- Add steps with **+ Add Step** button
- Each step has: Time, Title, Description

**Use Cases:**
- Attack chain documentation
- Incident timeline
- Testing methodology phases

---

#### Risk Matrix
**Icon:** `▣` | **Editor:** Yes

Visual likelihood × impact risk assessment grid.

**Editor Options:**

| Option | Description |
|--------|-------------|
| Matrix Size | 3×3 (Simple) or 5×5 (Detailed) |
| Highlighted Cell | Click to select risk position |

**3×3 Matrix Labels:**
- Likelihood: High, Medium, Low
- Impact: Low, Medium, High

**5×5 Matrix Labels:**
- Likelihood: Critical, High, Medium, Low, Info
- Impact: Rare, Unlikely, Possible, Likely, Certain

**Use Cases:**
- Overall engagement risk assessment
- Individual finding risk visualization
- Executive summary graphics

---

#### CVSS Score Card
**Icon:** `◉` | **Editor:** Yes

Visual CVSS score display with vector breakdown.

**Editor Options:**

| Option | Description |
|--------|-------------|
| CVSS Score | Numeric score (0.0-10.0) |
| CVSS Vector | Full vector string |

**Severity Colors:**

| Score Range | Severity | Color |
|-------------|----------|-------|
| 0.0 | None | Gray |
| 0.1-3.9 | Low | Blue |
| 4.0-6.9 | Medium | Yellow |
| 7.0-8.9 | High | Orange |
| 9.0-10.0 | Critical | Red |

**Vector Breakdown:** Automatically parses and displays Attack Vector, Attack Complexity, Privileges Required, User Interaction, Scope, and CIA Impact.

**Use Cases:**
- Individual finding severity cards
- Vulnerability scoring documentation
- Risk communication to stakeholders

---

### Export Options

| Format | Description |
|--------|-------------|
| **HTML** | Standalone HTML file with embedded styles |
| **Markdown** | Plain text Markdown format |
| **PDF** | Opens print dialog for PDF generation |
| **Word** | DOCX format for Microsoft Word |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New evidence (quick capture) |
| `Ctrl+F` | Focus search bar |
| `Ctrl+E` | Open export dialog |
| `Esc` | Close active modal |

---

## Security

### Data Protection

- **Local Storage**: All data stored in local SQLite database
- **Password Hashing**: Argon2id for user passwords and the database encryption key
- **Session Security**: JWT-based authentication tokens
- **No Cloud**: No external data transmission

### Best Practices

1. Use a strong admin password
2. Store the database file securely
3. Back up your database regularly
4. Use full-disk encryption on your system
5. Export and delete engagement data after project completion

---

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Please report security issues privately as described in [SECURITY.md](SECURITY.md).

## License

PTVault is open source under the [MIT License](LICENSE).

---

*PTVault - Secure your findings, streamline your reporting.*

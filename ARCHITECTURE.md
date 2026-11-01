# PTVault Architecture Document

## System Overview

PTVault is a local-first, encrypted web application for penetration testing evidence management. It runs as a Flask SPA served from a single `dashboard.html` page, backed by SQLite with FTS4 full-text search and WAL mode concurrency.

```
Architecture Style: Monolithic SPA + REST API
Runtime: Python 3.10+ / Flask 3.x
Database: SQLite 3.31+ (WAL mode, FTS4)
Frontend: Vanilla ES6+ JavaScript (no build step)
Styling: Tailwind CSS 3.x via CDN
Auth: Argon2id + JWT (httpOnly cookies)
```

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (SPA)                            │
│  templates/dashboard.html                                    │
│  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ static/js/  │ │ Tailwind │ │ D3.js v7 │ │ Lucide Icons│ │
│  │ 15 modules  │ │ CSS CDN  │ │ (maps)   │ │             │ │
│  └──────┬──────┘ └──────────┘ └──────────┘ └─────────────┘ │
│         │ API calls (fetch + auth_token cookie)              │
└─────────┼───────────────────────────────────────────────────┘
          │
          │ REST/JSON over HTTP
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Flask Application (app.py)                   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              Middleware Layer                           │  │
│  │  @require_auth → JWT verify → g.db + g.current_user   │  │
│  │  @require_role → admin / tester / viewer               │  │
│  │  @require_engagement_access → owner / editor / viewer  │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                   │
│  ┌────────────────────────▼───────────────────────────────┐  │
│  │              17 Flask Blueprints                        │  │
│  │  auth · engagements · evidence · hosts · reporting     │  │
│  │  testplans · commands · shell_oneliners · tags          │  │
│  │  admin · filters · users · engagement_members           │  │
│  │  relationships · attack_maps · templates · test         │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                   │
│  ┌────────────────────────▼───────────────────────────────┐  │
│  │              Utility Layer                              │  │
│  │  Tool Parsers (Nmap, Nessus, Burp, + 8 more)          │  │
│  │  Report Export (HTML, Markdown, PDF, DOCX)             │  │
│  │  Attack Map SVG Generator                               │  │
│  │  Script Generator (Bash/PowerShell)                     │  │
│  │  Host Extractor · File Helpers · Tag Migration          │  │
│  └────────────────────────┬───────────────────────────────┘  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  SQLite Database (ptvault.db)                 │
│                                                              │
│  WAL mode · FTS4 full-text search · Trigger-synced index     │
│  Versioned migrations (15 migrations in schema_migrations)   │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Users &  │ │Evidence &│ │ Hosts &  │ │ Reporting &   │  │
│  │ RBAC     │ │ Search   │ │ Targets  │ │ Templates     │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │Test Plans│ │ Attack   │ │ Commands │ │ Audit &       │  │
│  │& Atomics │ │ Maps     │ │& Shells  │ │ Sessions      │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Filesystem (./data/)                         │
│  uploads/evidence/{engagement_id}/   (screenshots, files)    │
│  atomics/atomic-red-team/            (Atomic Red Team lib)   │
└─────────────────────────────────────────────────────────────┘
```

---

## Authentication & Session Flow

```
┌──────────┐    POST /api/auth/login     ┌──────────────┐
│  Browser  │ ──── {username, password} ──▶│ routes/auth.py│
└──────────┘                              └───────┬──────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │ models/auth.py│
                                          │               │
                                          │ Argon2id      │
                                          │ time_cost=3   │
                                          │ memory=64MB   │
                                          │ parallelism=4 │
                                          └───────┬──────┘
                                                  │ verify_password()
                                                  ▼
                                          ┌──────────────┐
                                          │ JWT Created   │
                                          │ {user_id,     │
                                          │  role,        │
                                          │  username,    │
                                          │  exp: +24h}   │
                                          └───────┬──────┘
                                                  │
                                                  ▼
┌──────────┐    Set-Cookie: auth_token    ┌──────────────┐
│  Browser  │ ◀── httpOnly, SameSite=Lax ──│   Response   │
└─────┬────┘                              └──────────────┘
      │
      │  Every subsequent request includes cookie automatically
      ▼
┌──────────────────────────────────────────────────────────┐
│  middleware/auth.py: @require_auth                         │
│                                                           │
│  1. Extract auth_token from request.cookies               │
│  2. jwt.decode() with HS256                               │
│  3. Set g.current_user = user_id                          │
│  4. Set g.current_user_role = role                        │
│  5. Establish g.db = get_db_connection()                  │
│  6. Set g.active_engagement_id from session cookie        │
│  7. Proceed to route handler                              │
└──────────────────────────────────────────────────────────┘
```

---

## Request Lifecycle

```
Browser Request
      │
      ▼
 Flask Router (app.py)
      │
      ▼
 @require_auth (middleware/auth.py)
      │── Fail → 401 Unauthorized
      │
      ▼ (sets g.db, g.current_user, g.active_engagement_id)
 @require_role (optional)
      │── Fail → 403 Forbidden
      │
      ▼
 @require_engagement_access (optional)
      │── Fail → 403 Forbidden
      │
      ▼
 Route Handler (routes/*.py)
      │── g.db.cursor() → SQLite query
      │── Filter by g.active_engagement_id (data isolation)
      │── Business logic
      │
      ▼
 JSON Response → Browser
      │
      ▼
 @app.teardown_appcontext
      │── Close g.db connection
```

---

## Flask Blueprint Map

```
app.py
 │
 ├── /api/auth              auth_bp              Login, setup, logout
 ├── /api/engagements       engagements_bp       Project CRUD, active switching, export
 ├── /api/evidence          evidence_bp          Notes, files, search, tool import
 ├── /api/hosts             hosts_bp             Targets, ports, credentials, indicators
 ├── /api/reporting         reporting_bp         Reports, writeups, export (HTML/MD/PDF/DOCX)
 ├── /api/testplans         testplans_bp         MITRE ATT&CK, Atomic Red Team, executions
 ├── /api/commands          commands_bp          Command snippet database
 ├── /api/shell-oneliners   shell_oneliners_bp   Reverse shells, payloads
 ├── /api/tags              tags_bp              Tag autocomplete and management
 ├── /api/admin             admin_bp             Backup, CyberChef, system info
 ├── /api/filters           filters_bp           Saved filter configurations
 ├── /api/users             users_bp             Multi-user management (RBAC)
 ├── /api/engagements/*/members  engagement_members_bp  Team assignments
 ├── /api/relationships     relationships_bp     Node-to-node relationships
 ├── /api/attack-maps       attack_maps_bp       Visual attack map builder
 ├── /api/templates         templates_bp         Report template library
 └── /api/test              test_bp              Development/debug endpoints
```

---

## Database Schema (Entity Relationship)

### Users & Access Control

```
┌──────────────────┐       ┌─────────────────────┐
│      users       │       │ engagement_members   │
├──────────────────┤       ├─────────────────────┤
│ id (PK)          │◀──┐   │ id (PK)             │
│ username (UNIQUE)│   │   │ engagement_id (FK)──│──▶ engagements.id
│ email (UNIQUE)   │   ├───│ user_id (FK)        │
│ full_name        │   │   │ role                │    (owner/editor/viewer)
│ password_hash    │   │   │ added_by (FK)───────│──┐
│ role             │   │   └─────────────────────┘  │
│ is_active        │   │                             │
│ last_login       │   │   ┌─────────────────────┐  │
│ created_by (FK)──│───┘   │    audit_log        │  │
└──────────────────┘       ├─────────────────────┤  │
        ▲                  │ id (PK)             │  │
        │                  │ user_id (FK)────────│──┘
        │                  │ engagement_id (FK)  │
        │                  │ action              │
        │                  │ resource_type       │
        │                  │ resource_id         │
        │                  │ timestamp           │
        │                  └─────────────────────┘
        │
        │                  ┌─────────────────────┐
        └──────────────────│ user_sessions       │
                           ├─────────────────────┤
                           │ id (PK)             │
                           │ user_id (FK)        │
                           │ token_hash          │
                           │ expires_at          │
                           └─────────────────────┘
```

### Engagements, Evidence & Hosts (Core)

```
┌───────────────────┐
│   engagements     │
├───────────────────┤
│ id (PK)           │
│ name              │
│ client_name       │
│ status            │      ┌────────────────────┐
│ start_date        │      │    evidence        │
│ end_date          │      ├────────────────────┤
│ tags              │◀─────│ engagement_id (FK) │
└───────────────────┘      │ id (PK)            │
        │                  │ evidence_type      │
        │                  │ title              │
        │                  │ content            │
        │                  │ tags               │
        │                  │ file_path          │
        │                  │ metadata (JSON)    │
        │                  └────────┬───────────┘
        │                           │
        │                  ┌────────▼───────────┐
        │                  │  evidence_fts      │  (FTS4 virtual table)
        │                  │  title, content,   │  Synced by triggers:
        │                  │  metadata          │  INSERT/UPDATE/DELETE
        │                  └────────────────────┘
        │
        │                  ┌────────────────────┐
        │                  │   evidence_hosts   │  (junction table)
        │                  ├────────────────────┤
        │                  │ evidence_id (FK)───│──▶ evidence.id
        │                  │ host_id (FK)───────│──▶ hosts.id
        │                  └────────────────────┘
        │
        │                  ┌────────────────────┐
        └─────────────────▶│      hosts         │
                           ├────────────────────┤
                           │ id (PK)            │
                           │ engagement_id (FK) │
                           │ ip (UNIQUE w/ eng) │
                           │ hostname           │
                           │ os                 │
                           │ rooted             │  ◀── indicator flags
                           │ shell              │
                           │ interested         │
                           │ flagged            │
                           │ reviewed           │
                           │ color_category     │
                           └────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
           ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
           │  host_notes  │ │  host_ports  │ │host_credentials│
           ├──────────────┤ ├──────────────┤ ├────────────────┤
           │ host_id (FK) │ │ host_id (FK) │ │ host_id (FK)   │
           │ content (md) │ │ port         │ │ username       │
           └──────────────┘ │ protocol     │ │ password       │
                            │ state        │ │ password_type  │
                            │ service      │ │ hash_type      │
                            │ version      │ │ service        │
                            └──────────────┘ └────────────────┘
```

### Engagement Findings

```
┌───────────────────┐       ┌───────────────────────┐
│   engagements     │◀──────│ engagement_findings    │
└───────────────────┘       ├───────────────────────┤
                            │ id (PK)               │
                            │ engagement_id (FK)    │
                            │ title                 │
                            │ ip_address            │
                            │ hostname              │
                            │ criticality           │  (critical/high/medium/low)
                            │ cvss_score            │
                            │ finding_content       │
                            │ remediation_content   │
                            │ include_in_report     │
                            └───────────────────────┘
```

### Reporting

```
┌───────────────────┐       ┌───────────────────┐
│   engagements     │◀──────│     reports        │
└───────────────────┘       ├───────────────────┤
                            │ id (PK)           │
                            │ engagement_id (FK)│
                            │ name              │
                            │ structure_data    │  (JSON: section order + config)
                            └───────────────────┘

┌───────────────────┐       ┌───────────────────┐
│    writeups       │       │ report_templates  │
├───────────────────┤       ├───────────────────┤
│ id (PK)           │       │ id (PK)           │
│ name              │       │ name              │
│ writeup_type      │       │ description       │
│ category          │       │ default_sections  │
│ criticality       │       │ category          │
│ cvss_score        │       └───────────────────┘
│ description       │
│ remediation       │
│ tags              │
└───────────────────┘
```

### Test Plans & MITRE ATT&CK

```
┌───────────────────┐       ┌─────────────────────┐
│    test_plans     │◀──────│  test_plan_items     │
├───────────────────┤       ├─────────────────────┤
│ id (PK)           │       │ id (PK)             │
│ name              │       │ test_plan_id (FK)   │
│ description       │       │ atomic_id (FK)──────│──▶ atomics.id
│ target_platform   │       │ custom_name         │
│ tags              │       │ custom_command      │
└───────────────────┘       │ sort_order          │
                            │ enabled             │
                            └──────────┬──────────┘
                                       │
                            ┌──────────▼──────────┐
                            │  test_executions    │
                            ├─────────────────────┤
                            │ engagement_id (FK)  │──▶ engagements.id
                            │ test_plan_id (FK)   │
                            │ test_plan_item_id   │
                            │ host_id (FK)        │──▶ hosts.id
                            │ status              │    (pending/running/completed/failed)
                            │ execution_output    │
                            │ evidence_id (FK)    │──▶ evidence.id
                            └─────────────────────┘

┌───────────────────┐       ┌─────────────────────┐
│     atomics       │       │ atomics_metadata    │
├───────────────────┤       ├─────────────────────┤
│ id (PK)           │       │ id (PK, always 1)   │
│ technique_id      │       │ version             │
│ technique_name    │       │ last_updated        │
│ tactic            │       │ total_techniques    │
│ atomic_test_name  │       │ total_tests         │
│ executor_command  │       └─────────────────────┘
│ supported_platforms│
└───────────────────┘

┌───────────────────┐
│ navigator_layers  │
├───────────────────┤
│ id (PK)           │
│ name              │
│ domain            │
│ layer_json        │  (full ATT&CK Navigator JSON)
│ technique_count   │
└───────────────────┘
```

### Attack Maps

```
┌───────────────────┐
│   engagements     │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐       ┌─────────────────────┐
│   attack_maps     │◀──────│  attack_map_nodes    │
├───────────────────┤       ├─────────────────────┤
│ id (PK)           │       │ id (PK)             │
│ engagement_id (FK)│       │ map_id (FK)         │
│ name              │       │ node_type           │  action/condition/infrastructure
│ description       │       │ x, y               │  and/or/evidence_ref/finding_ref/host_ref
│ canvas_data (JSON)│       │ width, height       │
│ created_by (FK)   │       │ label               │
└───────────────────┘       │ properties (JSON)   │
         ▲                  │ ref_id, ref_type    │  (links to evidence/finding/host)
         │                  └─────────────────────┘
         │
         │                  ┌─────────────────────┐
         └──────────────────│  attack_map_edges    │
                            ├─────────────────────┤
                            │ id (PK)             │
                            │ map_id (FK)         │
                            │ source_node_id (FK) │──▶ attack_map_nodes.id
                            │ target_node_id (FK) │──▶ attack_map_nodes.id
                            │ label               │
                            └─────────────────────┘
```

### Relationships

```
┌─────────────────────────┐
│   node_relationships    │
├─────────────────────────┤
│ id (PK)                 │
│ source_node_id          │──▶ any table (evidence, hosts, findings)
│ source_type             │    (evidence/host/finding)
│ target_node_id          │──▶ any table
│ target_type             │
│ relationship_type       │    (relates_to/supports/contradicts/etc)
│ notes                   │
└─────────────────────────┘
```

---

## Frontend Module Architecture

```
templates/dashboard.html (SPA shell)
 │
 ├── static/js/app.js            Main init, tab switching, theme
 ├── static/js/auth.js           Login/setup forms
 ├── static/js/utils.js          Shared helpers (escapeHtml, debounce, etc.)
 │
 ├── static/js/hosts.js          Host list, indicators, ports, creds
 ├── static/js/reporting.js      Report builder, 20+ format tools, export
 ├── static/js/testplans.js      MITRE ATT&CK, Atomic Red Team
 ├── static/js/tools.js          MSFVenom, CVSS calc, CyberChef, Attack Maps tab
 ├── static/js/commands.js       Command database UI
 ├── static/js/admin.js          Backup, system settings
 ├── static/js/users.js          User management UI
 │
 ├── static/js/attack_map_editor.js   D3.js canvas editor (nodes + edges)
 │
 └── static/js/api.js            Central API facade
      │
      └── static/js/api/         Sub-modules (one per domain)
           ├── auth.js           AuthAPI
           ├── engagements.js    EngagementsAPI
           ├── evidence.js       EvidenceAPI
           ├── export.js         ExportAPI
           ├── hosts.js          HostsAPI
           ├── tags.js           TagsAPI
           ├── commands.js       CommandsAPI
           ├── admin.js          AdminAPI
           ├── shelloneliners.js ShellOnelinersAPI
           ├── reporting.js      ReportingAPI
           ├── testplans.js      TestPlansAPI
           ├── filters.js        FiltersAPI
           ├── relationships.js  RelationshipsAPI
           ├── users.js          UsersAPI
           ├── attack_maps.js    AttackMapsAPI
           └── lib/request.js    Base HTTP client (fetch wrapper)
```

---

## Tool Parser Pipeline

```
User uploads file (XML/JSON/CSV)
         │
         ▼
  detect_tool_type()          Examines root XML element / JSON structure
         │
         ├── <nmaprun>          → NmapParser
         ├── <issues>           → BurpParser
         ├── <NessusClientData> → NessusParser
         ├── <ASSET_DATA_REPORT>→ QualysParser
         ├── <ScanGroup>        → AcunetixParser
         ├── <OWASPZAPReport>   → ZapParser
         ├── JSON {sessions}    → MetasploitParser
         ├── JSON {results}     → NucleiParser
         ├── JSON {computers}   → BloodHoundParser
         └── CSV (CME format)   → CrackMapExecParser
         │
         ▼
  Parser.validate()           Confirms file structure
         │
         ▼
  Parser.parse()              Extracts standardized data:
         │                    { hosts: [], findings: [], metadata: {} }
         │
         ├──▶ Create/update hosts table entries
         ├──▶ Create host_ports entries
         ├──▶ Create evidence_hosts links
         ├──▶ Create engagement_findings
         ├──▶ Auto-generate tags
         └──▶ Store raw file in uploads/
```

---

## Report Export Pipeline

```
Report Builder (drag-and-drop workspace)
         │
         │  20+ Format Tools:
         │  Headers, Text, Lists, Code, Tables,
         │  Alert Boxes, Evidence Blocks, Risk Matrix,
         │  CVSS Cards, Timelines, Attack Maps, etc.
         │
         ▼
  Save Report → reports table (structure_data JSON)
         │
         ▼
  Export Request
         │
         ├──▶ HTML Export
         │    └── Standalone HTML with inline CSS
         │
         ├──▶ Markdown Export
         │    └── Plain text .md file
         │
         ├──▶ PDF Export
         │    └── HTML → WeasyPrint → PDF (or browser print)
         │
         └──▶ DOCX Export
              └── python-docx → Microsoft Word document

  Attack Map embedding:
    attack_maps → utils/attack_map_svg.py → inline SVG in report
```

---

## Data Isolation Model

```
All data queries are scoped by engagement_id:

  ┌─────────────────────────────────────────────────┐
  │              Engagement Boundary                  │
  │                                                   │
  │  evidence    WHERE engagement_id = ?              │
  │  hosts       WHERE engagement_id = ?              │
  │  findings    WHERE engagement_id = ?              │
  │  reports     WHERE engagement_id = ?              │
  │  attack_maps WHERE engagement_id = ?              │
  │  executions  WHERE engagement_id = ?              │
  │                                                   │
  │  Cross-engagement access requires admin role      │
  └─────────────────────────────────────────────────┘

  Global (shared across engagements):
  ─────────────────────────────────
  users, writeups, test_plans, atomics,
  navigator_layers, commands, shell_oneliners,
  report_templates
```

---

## RBAC Access Control

```
                    ┌─────────┐
                    │  admin  │  Global: full system access
                    └────┬────┘  Can manage users, all engagements
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────┐
         │ tester │ │ tester │ │ viewer │   Global roles
         └───┬────┘ └───┬────┘ └───┬────┘
             │          │          │
   Per-engagement roles (engagement_members table):
             │          │          │
         ┌───▼───┐  ┌──▼────┐  ┌─▼──────┐
         │ owner │  │editor │  │ viewer  │
         │       │  │       │  │         │
         │ Full  │  │Modify │  │Read-only│
         │control│  │ data  │  │ access  │
         └───────┘  └───────┘  └─────────┘
```

---

## File System Layout

```
ptvault/
├── app.py                      Flask entry point, blueprint registration
├── config.py                   Environment config (SECRET_KEY, DB_PATH, etc.)
├── requirements.txt            Python dependencies
│
├── models/
│   ├── auth.py                 Argon2id hashing, JWT creation/verification
│   ├── database.py             SQLite connection, init_db(), migrations
│   ├── schema.sql              Base schema (users, evidence, hosts, etc.)
│   ├── dao/                    Data Access Objects (BaseDAO pattern)
│   │   ├── base.py             BaseDAO with engagement scoping
│   │   ├── attack_map_dao.py   AttackMap/Node/Edge DAOs
│   │   ├── relationship_dao.py Relationship + AttackPath DAOs
│   │   └── ...                 (8 more DAO classes)
│   └── migrations/
│       ├── manager.py          Migration runner (version tracking)
│       └── versions/           15 versioned migration files
│           ├── 001_initial_schema.py
│           ├── ...
│           ├── 012_multi_user_support.py
│           └── 015_attack_maps.py
│
├── middleware/
│   └── auth.py                 @require_auth, @require_role, @require_engagement_access
│
├── routes/                     17 Flask blueprints
│   ├── auth.py                 /api/auth (setup, login, logout)
│   ├── engagements.py          /api/engagements (CRUD, findings, export)
│   ├── evidence.py             /api/evidence (CRUD, search, file upload)
│   ├── hosts.py                /api/hosts (CRUD, ports, creds, indicators)
│   ├── reporting.py            /api/reporting (reports, writeups, export)
│   ├── testplans.py            /api/testplans (ATT&CK, atomics, executions)
│   ├── attack_maps.py          /api/attack-maps (maps, nodes, edges, SVG)
│   ├── commands.py             /api/commands
│   ├── shell_oneliners.py      /api/shell-oneliners
│   ├── users.py                /api/users (RBAC user management)
│   ├── engagement_members.py   /api/engagements/*/members
│   ├── admin.py                /api/admin (backup, system info)
│   ├── tags.py                 /api/tags (autocomplete)
│   ├── filters.py              /api/filters (saved filters)
│   ├── relationships.py        /api/relationships
│   └── templates.py            /api/templates
│
├── utils/
│   ├── parsers/                Tool output parsers
│   │   ├── nmap_parser.py      Nmap XML → hosts + ports
│   │   ├── nessus_parser.py    Nessus XML → vulnerabilities
│   │   ├── burp_parser.py      Burp Suite XML → findings
│   │   └── ...                 (8 more parsers)
│   ├── attack_map_svg.py       Server-side SVG generator for reports
│   ├── script_generator.py     Bash/PowerShell test script generator
│   ├── markdown_export.py      Report → Markdown conversion
│   ├── host_extractor.py       IP/hostname extraction from text
│   └── file_helpers.py         Upload sanitization, path helpers
│
├── templates/
│   ├── dashboard.html          Main SPA (all features in one page)
│   ├── login.html              Login page
│   └── setup.html              First-time setup wizard
│
├── static/
│   ├── css/main.css            Custom CSS design system (CSS variables)
│   └── js/
│       ├── app.js              SPA init, tab switching, theme
│       ├── api.js              Central API facade (imports all sub-modules)
│       ├── api/                15 API sub-modules
│       │   ├── lib/request.js  Base HTTP client
│       │   ├── auth.js         AuthAPI
│       │   ├── evidence.js     EvidenceAPI
│       │   ├── hosts.js        HostsAPI
│       │   ├── reporting.js    ReportingAPI
│       │   ├── attack_maps.js  AttackMapsAPI
│       │   └── ...             (9 more API modules)
│       ├── hosts.js            Host management UI
│       ├── reporting.js        Report builder (drag-and-drop, 20+ format tools)
│       ├── tools.js            Built-in utilities (MSFVenom, CVSS, etc.)
│       ├── attack_map_editor.js D3.js visual map editor
│       ├── testplans.js        MITRE ATT&CK / Atomic Red Team
│       ├── commands.js         Command database UI
│       └── utils.js            Shared helpers
│
└── data/                       Runtime data (gitignored)
    ├── ptvault.db              SQLite database
    └── uploads/
        ├── evidence/           Uploaded files per engagement
        └── atomics/            Atomic Red Team library
```

---

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.10+ | Server-side logic |
| **Framework** | Flask 3.x | Web framework, blueprints, routing |
| **Database** | SQLite 3.31+ | Local storage, WAL mode, FTS4 search |
| **Auth** | Argon2id | Password hashing (time=3, mem=64MB) |
| **Sessions** | JWT (HS256) | httpOnly cookie, 24h expiry |
| **XML Security** | defusedxml | XXE prevention for tool parsers |
| **Reports** | python-docx, WeasyPrint | DOCX and PDF generation |
| **Frontend** | Vanilla ES6+ JS | SPA, no build step, no framework |
| **Styling** | Tailwind CSS 3.x CDN + Custom CSS vars | Responsive dark-mode UI |
| **Visualization** | D3.js v7 | Attack map canvas (SVG) |
| **Icons** | Lucide Icons | Modern iconography |
| **Deployment** | Docker / PyInstaller | Container or standalone binary |

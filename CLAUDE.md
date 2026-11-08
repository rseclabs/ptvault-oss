# PTVault - Penetration Testing Evidence Manager

PTVault is a secure, local-first workspace for penetration testers to manage engagements, collect evidence, track findings, and generate professional reports. All data is stored locally in SQLite with no cloud dependencies, making it suitable for air-gapped environments and sensitive client work. Supports multi-user RBAC with team-based engagement access.

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Runtime | Python | 3.10+ | Server-side logic and API |
| Framework | Flask | 3.x | Web framework with Blueprint-based routing |
| Database | SQLite + SQLCipher | 3.31+ | Local storage, encrypted at rest (`sqlcipher3`), FTS4 full-text search, WAL mode |
| Auth | Argon2id + JWT | - | Password hashing (time_cost=3, memory=64MiB) and HS256 session tokens |
| Crypto | PyNaCl | 1.5+ | Cryptographic operations |
| Parsers | lxml, defusedxml, python-libnmap | - | Secure XML/JSON tool output parsing (11 tools supported) |
| Reports | python-docx, WeasyPrint | 1.1+, 60+ | Word and PDF document generation |
| Frontend | Vanilla JS | ES6+ | Single-page application (no build step) |
| Styling | CSS custom properties | - | `static/css/main.css` token system, light and dark themes |
| Front-end libraries | Lucide, D3, marked, EasyMDE, Inter | pinned | Vendored in `static/vendor/`; nothing loads from a CDN |

## Quick Start

```bash
# Prerequisites: Python 3.10+

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
# Access at http://localhost:5001
```

**First-time setup:** Navigate to http://localhost:5001. Until an account exists, `/` redirects to the setup wizard: create the initial admin account (full name, email, password of at least 8 characters), then log in.

**Docker:** `docker compose up -d` -- Access at http://localhost:5000

## Project Structure

```
ptvault/
├── app.py                 # Flask entry point, web UI routes, CSRF and security headers
├── config.py              # Configuration (env vars, paths, upload limits)
├── features.py            # Blueprint registry (BLUEPRINTS list of route modules)
├── requirements.txt       # 14 Python dependencies
│
├── models/
│   ├── auth.py            # Argon2id hashing, JWT creation/verification
│   ├── database.py        # Connection, init_db, setup_required, migrations entry
│   ├── encryption.py      # SQLCipher key handling, plaintext <-> encrypted export
│   ├── schema.sql         # Base schema (21 tables, FTS4, triggers, indexes)
│   ├── seed_templates.py  # Report template seeding
│   ├── seed_shell_oneliners.py # Built-in shell one-liners (restored on every start)
│   ├── dao/               # Data Access Objects (13 DAOs + BaseDAO)
│   │   ├── base.py        # BaseDAO with common CRUD
│   │   ├── engagement_dao.py, evidence_dao.py, host_dao.py, user_dao.py
│   │   ├── team_dao.py, client_dao.py, dashboard_dao.py, note_tree_dao.py
│   │   ├── report_dao.py, template_dao.py, test_plan_dao.py
│   │   └── relationship_dao.py, attack_map_dao.py
│   └── migrations/        # Versioned migration system
│       ├── manager.py     # MigrationManager class
│       └── versions/      # 30 migration files (001-031)
│
├── routes/                # Flask Blueprints (20, registered in features.py)
│   ├── auth.py            # /api/auth/* - Login, setup, logout, CSRF token
│   ├── dashboard.py       # /api/dashboard/* - Engagement dashboard data
│   ├── engagements.py     # /api/engagements/* - Projects, export
│   ├── engagement_members.py # /api/engagements/<id>/members - Team access
│   ├── evidence.py        # /api/evidence/* - Notes, files, search, filter
│   ├── hosts.py           # /api/hosts/* - Targets, ports, creds
│   ├── reporting.py       # /api/reporting/* - Reports, writeups
│   ├── templates.py       # /api/templates/* - Report templates
│   ├── testplans.py       # /api/testplans/* - MITRE ATT&CK, Atomics
│   ├── commands.py        # /api/commands/* - Command database
│   ├── shell_oneliners.py # /api/shell-oneliners/* - Shell snippets
│   ├── tags.py            # /api/tags/* - Tag autocomplete
│   ├── filters.py         # /api/filters/* - Saved filters, CIDR support
│   ├── users.py           # /api/users/* - Multi-user management
│   ├── teams.py           # /api/teams/* - Teams
│   ├── clients.py         # /api/clients/* - Client records
│   ├── relationships.py   # /api/relationships/* - Node relationships
│   ├── attack_maps.py     # /api/attack-maps/* - Attack map visualization
│   ├── admin.py           # /api/admin/* - Backup, settings, CyberChef
│   └── test.py            # /api/test/* - Development testing
│
├── middleware/
│   └── auth.py            # @require_auth, @require_role, @require_engagement_access
│
├── utils/
│   ├── parsers/           # Tool output parsers (11 tools + base + registry)
│   │   ├── base_parser.py     # BaseToolParser abstract class
│   │   ├── registry.py        # Parser auto-discovery and routing
│   │   ├── nmap, nessus, burp, zap, qualys, nuclei, metasploit,
│   │   └── acunetix, insightvm, bloodhound, crackmapexec (*_parser.py)
│   ├── attack_map_svg.py     # SVG generation for attack maps
│   ├── audit_logger.py       # Audit logging for compliance
│   ├── error_handler.py      # Centralized error handling
│   ├── pdf_generator.py      # PDF report generation (WeasyPrint)
│   ├── report_auto_populator.py # Auto-populate reports from findings
│   ├── template_renderer.py  # Report template rendering
│   ├── script_generator.py   # Bash/PowerShell test scripts
│   ├── atomics_downloader.py, atomics_parser.py # Atomic Red Team
│   ├── navigator_parser.py   # MITRE Navigator layers
│   ├── session_log_parser.py # Session log imports
│   ├── markdown_export.py    # Report export to Markdown
│   ├── host_extractor.py     # IP/hostname extraction
│   └── helpers.py, file_helpers.py, migration_tags.py
│
├── templates/
│   ├── dashboard.html     # Main SPA (all sections)
│   ├── login.html         # Login page
│   ├── setup.html         # First-time setup wizard
│   ├── note_editor.html, finding_editor.html # Standalone editors
│   └── reports/           # Report templates
│
├── static/
│   ├── css/main.css, dashboard.css # Design tokens (:root, [data-theme="dark"]) and styles
│   ├── js/                # Section modules: app, hosts, reporting, testplans, tools,
│   │                      #   dashboard, attack_map_editor, notes_tree, commands, users, ...
│   ├── js/api/            # API layer (18 modules), re-exported by js/api.js
│   ├── js/lib/            # request.js, idle-timeout.js
│   ├── vendor/            # Pinned third-party libraries and fonts (see vendor/README.md)
│   └── tools/cyberchef/   # Bundled CyberChef
│
├── tests/                 # pytest suite (unit, DAO, parser, route, security)
│   ├── conftest.py, dao/, parsers/, fixtures/, e2e/
│   └── test_*.py
│
└── data/                  # Runtime (gitignored)
    ├── ptvault.db         # SQLite database (SQLCipher-encrypted after setup)
    ├── encryption.key, encryption.salt
    ├── uploads/           # Evidence files
    └── atomics/           # Atomic Red Team library
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (SPA)                        │
│  dashboard.html + static/js + static/css + static/vendor │
└─────────────────────────┬───────────────────────────────┘
                          │ REST API (JSON)
┌─────────────────────────▼───────────────────────────────┐
│                    Flask Application                     │
│  app.py → features.py (20 Blueprints) → @require_auth    │
│         → DAO layer                                      │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│         SQLite / SQLCipher + FTS4 (WAL mode)            │
│  data/ptvault.db • schema.sql + migrations • FTS index  │
└─────────────────────────────────────────────────────────┘
```

### Key Modules

| Module | Location | Purpose |
|--------|----------|---------|
| Engagement Management | `routes/engagements.py` | Create/edit projects, export data |
| Evidence Collection | `routes/evidence.py` | Store notes, screenshots, tool imports |
| Host Tracking | `routes/hosts.py` | Target IPs, ports, credentials, indicators |
| Report Builder | `routes/reporting.py` | Drag-and-drop report generation |
| Test Plans | `routes/testplans.py` | MITRE ATT&CK, Atomic Red Team integration |
| User Management | `routes/users.py`, `routes/teams.py` | Multi-user RBAC (admin, editor, viewer) |
| Attack Maps | `routes/attack_maps.py` | Visual attack path mapping with SVG export |
| Relationships | `routes/relationships.py` | Universal node relationships between entities |
| Tool Parsers | `utils/parsers/` | 11 parsers: Nmap, Nessus, Burp, ZAP, Nuclei, etc. |
| DAO Layer | `models/dao/` | Data access objects for all entities |
| Migrations | `models/migrations/` | Versioned schema migrations (001-031) |
| Encryption | `models/encryption.py` | SQLCipher keying and migration to/from encrypted |

### Core Tables

A selection; `models/schema.sql` plus the migrations are the full schema.

| Table | Purpose |
|-------|---------|
| `users` | Multi-user with RBAC (admin, editor, viewer roles) |
| `user_sessions` | Active session tracking with token hashes |
| `audit_log` | Security/compliance audit trail |
| `engagements` | Client projects with status, dates, contacts |
| `engagement_members` | Team-based engagement access control |
| `evidence` | Notes, screenshots, tool output with metadata JSON |
| `evidence_fts` | FTS4 virtual table for full-text search |
| `hosts` | Target systems with indicators (rooted, shell, etc.) |
| `host_ports` | Port scan results |
| `host_credentials` | Discovered credentials |
| `host_notes` | Per-host markdown notes |
| `test_plans` / `test_plan_items` | Atomic Red Team test collections |
| `test_executions` | Engagement-specific test execution tracking |
| `atomics` / `atomics_metadata` | Atomic Red Team library cache |
| `navigator_layers` | MITRE ATT&CK Navigator layers |

## Development Guidelines

### Code Style

**Python (Backend):**
- File names: `snake_case.py` (e.g., `nmap_parser.py`, `host_extractor.py`)
- Functions: `snake_case` (e.g., `get_db_connection`, `verify_master_password`)
- Classes: `PascalCase` (e.g., `NmapToolParser`, `BaseDAO`, `MigrationManager`)
- Variables: `snake_case` (e.g., `engagement_id`, `host_data`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `MAX_FILE_SIZE`, `JWT_EXPIRY_HOURS`)
- Blueprint names: `snake_case` with `_bp` suffix (e.g., `engagements_bp`, `auth_bp`)

**JavaScript (Frontend):**
- File names: `lowercase.js` or `snake_case.js` (e.g., `api.js`, `attack_map_editor.js`)
- Variables/Functions: `camelCase` (e.g., `loadHosts`, `activeEngagement`)
- Constants: `SCREAMING_SNAKE` when applicable
- Global objects: `PascalCase` (e.g., `API`, `Utils`)

**CSS and icons:**
- Every colour and font goes through a custom property in `static/css/main.css` (`:root` and `[data-theme="dark"]`); no literal values in rules
- Icons are Lucide (`<i data-lucide="name"></i>`); on the dashboard, icons added to the DOM later are drawn automatically. No emoji as icons
- Font Awesome is present only for EasyMDE's toolbar; create editors with `autoDownloadFontAwesome: false`
- Gradients are allowed. Finding and scan cards keep their severity gradient (a soft severity tint fading across the card) and a 4px severity left edge; do not flatten them
- Severity colours: critical purple, high red, medium orange, low yellow (`--sev-*` in `static/css/tokens.css`), the same in every view and in both themes

### Import Order

```python
# 1. Standard library
import os
import json
from datetime import datetime

# 2. Third-party packages
from flask import Blueprint, request, jsonify, g
from argon2 import PasswordHasher

# 3. Local application imports
from config import Config
from models.database import get_db_connection
from middleware.auth import require_auth
```

### API Patterns

```python
# All routes under /api/ with @require_auth
@require_auth
def get_hosts():
    cursor = g.db.cursor()
    # Always filter by engagement_id for data isolation
    cursor.execute('SELECT * FROM hosts WHERE engagement_id = ?',
                   (g.active_engagement_id,))
```

- JSON request/response bodies
- Error responses: `{"error": "message"}` with appropriate HTTP status
- `@require_auth` sets `g.db`, `g.current_user`, `g.current_user_role`
- `@require_role('admin')` restricts to specific roles
- `@require_engagement_access('editor')` checks team membership with role hierarchy
- Mutating requests need the double-submit CSRF token: the `csrf_token` cookie echoed in an `X-CSRF-Token` header

### Adding Features

1. Create Blueprint in `routes/new_feature.py`
2. Register it in `features.py`: add `('routes.new_feature', 'new_feature_bp')` to `BLUEPRINTS`
3. Add `@require_auth` to protected endpoints
4. Create DAO in `models/dao/new_feature_dao.py` if needed
5. Add migration in `models/migrations/versions/NNN_description.py`
6. Create JS module in `static/js/new_feature.js`
7. Add API module in `static/js/api/new_feature.js`, import in `static/js/api.js`
8. Update `dashboard.html` with UI section

### Third-party front-end code

Never load a script, stylesheet or font from a CDN: PTVault must run air-gapped, and the Content-Security-Policy in `app.py` allows no external host for them. Vendor a pinned release under `static/vendor/<name>-<version>/` with its license, following `static/vendor/README.md`. `tests/test_security.py` fails if a template references an external asset.

## Commands

| Command | Description |
|---------|-------------|
| `python app.py` | Dev server on port 5001 (`-i` interface, `-p` port) |
| `python -m pytest tests/ -v` | Run test suite |
| `docker compose up -d` | Docker deployment (port 5000) |
| `./build_docker.sh build` | Build Docker image |
| `./build_pyinstaller.sh` | Build standalone binary |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Generated once into `flask_secret.key` beside the database | Flask secret key; startup refuses placeholders or < 32 bytes |
| `DATABASE_PATH` | `./data/ptvault.db` | SQLite database path |
| `JWT_SECRET_KEY` | Generated once into `jwt_secret.key` beside the database | JWT signing key (HS256); same checks |
| `JWT_EXPIRY_HOURS` | `24` | Session token lifetime |
| `ENVIRONMENT` | `development` | `development` or `production` (production: Secure cookies, HSTS, no debugger) |
| `PTVAULT_ENCRYPTION_KEY_FILE` | `encryption.key` beside the database | SQLCipher key file |
| `PTVAULT_ENCRYPTION_SALT_FILE` | `encryption.salt` beside the database | Key derivation salt |
| `PTVAULT_ENCRYPTION_REQUIRED` | unset | `true` refuses to start without SQLCipher |

Copy `.env.example` to `.env` and customize for production. When running a second instance or a smoke test, point every data path (database, key, salt, uploads) somewhere else, or the instance can overwrite the real key.

## Testing

```bash
python -m pytest tests/ -v
```

- **Parser tests:** `tests/test_nmap_parser.py`, `tests/parsers/`
- **DAO tests:** `tests/dao/` (including FTS search and tag filtering)
- **Integration tests:** `tests/test_multi_user.py`, `tests/test_rbac.py`, `tests/test_testplans_routes.py`
- **Security tests:** `tests/test_security.py` (headers, CSP, CSRF, no external assets)
- **Migration and encryption tests:** `tests/test_migrations.py`, `tests/test_encryption.py`
- **Fixtures:** `tests/fixtures/` - sample XML/JSON data for parser tests

Tests cannot import `app.py` (it opens the configured database on import); put logic a test needs in a module it can import, as `setup_required()` in `models/database.py` is.

## Security

- Argon2id: time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=4, hash_len=32
- Database encrypted at rest with SQLCipher once setup runs; key and salt live beside the database
- JWT (HS256) in httpOnly cookies (XSS protection); double-submit CSRF token on mutating API calls
- RBAC: admin, editor, viewer roles with engagement-level access control
- Audit logging for security-sensitive actions
- defusedxml prevents XXE attacks in all XML parsers
- Max upload: 250MB (`Config.MAX_FILE_SIZE`)
- Allowed extensions: `.txt`, `.xml`, `.json`, `.png`, `.jpg`, `.jpeg`, `.pdf`, `.html`, `.log`, `.pcap`, `.nessus`
- Data isolation by engagement_id with team membership checks
- No default account: the first admin is created in the setup wizard

## Key Files Reference

| File | Purpose |
|------|---------|
| `features.py` | Blueprint registry (`BLUEPRINTS` list) |
| `app.py` | Web UI routes (`index`, `setup`, `dashboard`, editors), `csrf_protect`, `set_security_headers` |
| `utils/security_headers.py` | Security headers and CSP for every response; `untrusted_response_headers` sandboxes uploaded files and exported report HTML |
| `middleware/auth.py` | `require_auth`, `require_role`, `require_engagement_access` |
| `models/database.py` | `get_db_connection`, `setup_required`, `init_db` |
| `models/encryption.py` | SQLCipher keying, `migrate_to_plaintext`, encrypted export |
| `models/migrations/manager.py` | Versioned migration runner |
| `models/auth.py` | Argon2id parameters, JWT creation and verification |
| `models/schema.sql` | Base schema (FTS4, triggers) |
| `utils/parsers/registry.py` | Parser auto-discovery and routing |
| `utils/parsers/base_parser.py` | `BaseToolParser` abstract class for all parsers |
| `static/vendor/README.md` | Pinned front-end libraries, licenses, checksums, update steps |

## Skills

Claude Code skills are defined in `.claude/skills/` for specialized assistance:

| Skill | Use When |
|-------|----------|
| `sqlite` | Schema design, FTS4, migrations, queries |
| `flask` | Blueprints, routing, middleware, request handling |
| `javascript` | SPA logic, DOM manipulation, API integration |
| `python` | Routes, models, authentication, backend logic |
| `frontend-design` | CSS tokens, responsive layouts, dark mode |
| `jwt` | Token generation, validation, session auth |
| `argon2` | Password hashing, verification |
| `pynacl` | Cryptographic operations |
| `pytest` | Test structure and fixtures |
| `docker` | Container builds, compose configs |
| `xml-parsing` | Nmap, Nessus, Burp XML parsing |
| `tailwind` | Legacy: the app no longer uses Tailwind; styles are plain CSS with custom properties |

## Specialized Agents

Agents in `.claude/agents/` for specific workflows:

| Agent | Purpose |
|-------|---------|
| `backend-engineer` | Flask API development, database, parsers |
| `frontend-engineer` | Vanilla JS SPA, API integration |
| `test-engineer` | Unit tests, integration tests |
| `debugger` | Flask routes, SQLite, JWT, parser debugging |
| `designer` | CSS tokens, dark mode, responsive layouts |
| `devops-engineer` | Docker, PyInstaller, systemd |
| `security-engineer` | Argon2, JWT, XXE prevention, file security |
| `data-engineer` | SQLite schema, FTS4, migrations |
| `documentation-writer` | README, API docs, feature guides |
| `code-reviewer` | Python patterns, JS quality, security |
| `refactor-agent` | Code consolidation, module organization |

## Documentation

- @README.md - Full user documentation with screenshots
- @QUICKSTART.md - Getting started guide
- @DEPLOYMENT.md - Production deployment instructions
- @PACKAGING.md - Build options (PyInstaller, Docker)
- @FEATURE_INDICATORS.md - Host indicator system

## Skill Usage Guide

When working on tasks involving these technologies, invoke the corresponding skill:

| Skill | Invoke When |
|-------|-------------|
| sqlite | Designs SQLite schema, FTS4 indexes, migrations, and query optimization |
| python | Manages Flask routes, models, authentication, backend logic, and utility functions |
| flask | Configures Flask blueprints, routing, middleware, and request handling patterns |
| javascript | Handles vanilla JavaScript SPA logic, DOM manipulation, and API integration |
| frontend-design | Applies UI styling with CSS custom properties, dark mode support, and responsive layouts |
| jwt | Manages JWT token generation, validation, and session authentication in httpOnly cookies |
| argon2 | Implements Argon2id password hashing and verification for user passwords and the database encryption key |
| xml-parsing | Secures XML parsing for Nmap, Nessus, and Burp Suite tool imports |
| docker | Builds Docker images and compose configurations for containerized deployment |
| pynacl | Handles cryptographic operations and secure data encryption |
| pytest | Structures unit tests, integration tests, and test fixtures for validation |

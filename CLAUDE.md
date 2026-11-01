# PTVault - Penetration Testing Evidence Manager

PTVault is a secure, local-first workspace for penetration testers to manage engagements, collect evidence, track findings, and generate professional reports. All data is stored locally in SQLite with no cloud dependencies, making it suitable for air-gapped environments and sensitive client work. Supports multi-user RBAC with team-based engagement access.

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Runtime | Python | 3.10+ | Server-side logic and API |
| Framework | Flask | 3.x | Web framework with Blueprint-based routing |
| Database | SQLite | 3.31+ | Local storage with FTS4 full-text search, WAL mode |
| Auth | Argon2id + JWT | - | Password hashing (time_cost=3, memory=64MiB) and HS256 session tokens |
| Crypto | PyNaCl | 1.5+ | Cryptographic operations |
| Parsers | lxml, defusedxml, python-libnmap | - | Secure XML/JSON tool output parsing (11 tools supported) |
| Reports | python-docx, WeasyPrint | 1.1+, 60+ | Word and PDF document generation |
| Frontend | Vanilla JS | ES6+ | Single-page application (no build step) |
| Styling | Tailwind CSS | 3.x | Utility-first CSS via CDN |

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

**First-time setup:** Navigate to http://localhost:5001, create the initial admin account (email + password, min 8 characters), then log in.

**Docker:** `docker compose up -d` -- Access at http://localhost:5000

## Project Structure

```
ptvault/
├── app.py                 # Flask entry point, blueprint registration via features.py
├── config.py              # Configuration (env vars, paths, upload limits)
├── features.py            # Blueprint registry (single list of route modules)
├── requirements.txt       # 12 Python dependencies
│
├── models/
│   ├── auth.py            # Argon2id hashing, JWT creation/verification
│   ├── database.py        # SQLite connection, init_db, seeding
│   ├── schema.sql         # 19 tables, FTS4, triggers, indexes
│   ├── seed_templates.py  # Report template seeding
│   ├── dao/               # Data Access Objects (10 DAOs)
│   │   ├── base.py        # BaseDAO with common CRUD
│   │   ├── engagement_dao.py
│   │   ├── evidence_dao.py
│   │   ├── host_dao.py
│   │   ├── user_dao.py
│   │   ├── report_dao.py
│   │   ├── test_plan_dao.py
│   │   ├── template_dao.py
│   │   ├── relationship_dao.py
│   │   └── attack_map_dao.py
│   └── migrations/        # Versioned migration system
│       ├── manager.py     # MigrationManager class
│       └── versions/      # 15 migration files (001-015)
│
├── routes/                # Flask Blueprints (17 API endpoints)
│   ├── auth.py            # /api/auth/* - Login, setup, logout
│   ├── engagements.py     # /api/engagements/* - Projects, export
│   ├── evidence.py        # /api/evidence/* - Notes, files, search
│   ├── hosts.py           # /api/hosts/* - Targets, ports, creds
│   ├── reporting.py       # /api/reporting/* - Reports, writeups
│   ├── testplans.py       # /api/testplans/* - MITRE ATT&CK, Atomics
│   ├── commands.py        # /api/commands/* - Command database
│   ├── shell_oneliners.py # /api/shell-oneliners/* - Shell snippets
│   ├── admin.py           # /api/admin/* - Backup, CyberChef
│   ├── tags.py            # /api/tags/* - Tag autocomplete
│   ├── templates.py       # /api/templates/* - Report templates
│   ├── filters.py         # /api/filters/* - Saved filters, CIDR support
│   ├── users.py           # /api/users/* - Multi-user management
│   ├── engagement_members.py # /api/engagements/<id>/members - Team access
│   ├── relationships.py   # /api/relationships/* - Node relationships
│   ├── attack_maps.py     # /api/attack-maps/* - Attack map visualization
│   └── test.py            # /api/test/* - Development testing
│
├── middleware/
│   └── auth.py            # @require_auth, @require_role, @require_engagement_access
│
├── utils/
│   ├── parsers/           # Tool output parsers (11 tools + base + registry)
│   │   ├── base_parser.py     # BaseParser abstract class
│   │   ├── registry.py        # Parser auto-discovery and routing
│   │   ├── nmap_parser.py     # Nmap XML → hosts, ports
│   │   ├── nessus_parser.py   # Nessus XML → vulnerabilities
│   │   ├── burp_parser.py     # Burp Suite XML → findings
│   │   ├── zap_parser.py      # OWASP ZAP XML → findings
│   │   ├── qualys_parser.py   # Qualys XML → vulnerabilities
│   │   ├── nuclei_parser.py   # Nuclei JSON → findings
│   │   ├── metasploit_parser.py    # Metasploit XML → sessions/vulns
│   │   ├── acunetix_parser.py      # Acunetix XML → web findings
│   │   ├── insightvm_parser.py     # InsightVM/Nexpose XML → vulns
│   │   ├── bloodhound_parser.py    # BloodHound JSON → AD paths
│   │   └── crackmapexec_parser.py  # CrackMapExec JSON → creds/shares
│   ├── attack_map_svg.py     # SVG generation for attack maps
│   ├── audit_logger.py       # Audit logging for compliance
│   ├── error_handler.py      # Centralized error handling
│   ├── pdf_generator.py      # PDF report generation (WeasyPrint)
│   ├── report_auto_populator.py # Auto-populate reports from findings
│   ├── template_renderer.py  # Report template rendering
│   ├── script_generator.py   # Bash/PowerShell test scripts
│   ├── atomics_downloader.py # Atomic Red Team fetcher
│   ├── atomics_parser.py     # Atomics YAML parser
│   ├── navigator_parser.py   # MITRE Navigator layers
│   ├── markdown_export.py    # Report export to Markdown
│   ├── host_extractor.py     # IP/hostname extraction
│   ├── file_helpers.py       # File utilities
│   └── migration_tags.py     # Tag migration helpers
│
├── templates/
│   ├── dashboard.html     # Main SPA (~126KB, all features)
│   ├── login.html         # Login page
│   ├── setup.html         # First-time setup wizard
│   ├── note_editor.html   # Standalone note editor
│   └── reports/           # Report templates
│
├── static/js/             # Frontend modules (~20K lines total)
│   ├── app.js             # Main application logic (1,272 lines)
│   ├── api.js             # API facade (imports from api/ modules)
│   ├── api/               # Modular API layer (15 modules)
│   │   ├── auth.js        ├── engagements.js  ├── evidence.js
│   │   ├── hosts.js       ├── reporting.js    ├── testplans.js
│   │   ├── commands.js    ├── admin.js        ├── tags.js
│   │   ├── export.js      ├── filters.js      ├── shelloneliners.js
│   │   ├── users.js       ├── relationships.js└── attack_maps.js
│   ├── hosts.js           # Host management UI (3,619 lines)
│   ├── reporting.js       # Report builder UI (3,557 lines)
│   ├── testplans.js       # Test plans UI (2,742 lines)
│   ├── tools.js           # Built-in utilities UI (2,635 lines)
│   ├── attack_map_editor.js # Attack map builder (1,096 lines)
│   ├── relationship_graph.js # Relationship graph visualization
│   ├── commands.js        # Command database UI
│   ├── users.js           # User management UI
│   ├── auth.js            # Authentication UI
│   ├── admin.js           # Admin functions
│   └── utils.js           # Shared utilities
│
├── tests/                 # Test suite
│   ├── conftest.py        # Pytest configuration
│   ├── test_nmap_parser.py
│   ├── test_migrations.py
│   ├── test_multi_user.py
│   ├── test_rbac.py
│   ├── test_relationships.py
│   ├── test_report_templates.py
│   ├── dao/               # DAO unit tests
│   ├── parsers/           # Parser tests
│   └── fixtures/          # Test data
│
└── data/                  # Runtime (gitignored)
    ├── ptvault.db         # SQLite database
    ├── uploads/           # Evidence files
    └── atomics/           # Atomic Red Team library
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Browser (SPA)                        │
│  dashboard.html + static/js/*.js + Tailwind CSS CDN     │
└─────────────────────────┬───────────────────────────────┘
                          │ REST API (JSON)
┌─────────────────────────▼───────────────────────────────┐
│                    Flask Application                     │
│  app.py → 17 Blueprints → @require_auth → DAO layer    │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│              SQLite + FTS4 (WAL mode)                   │
│  data/ptvault.db • 19 tables • Triggers sync FTS index  │
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
| User Management | `routes/users.py` | Multi-user RBAC (admin, editor, viewer) |
| Attack Maps | `routes/attack_maps.py` | Visual attack path mapping with SVG export |
| Relationships | `routes/relationships.py` | Universal node relationships between entities |
| Tool Parsers | `utils/parsers/` | 11 parsers: Nmap, Nessus, Burp, ZAP, Nuclei, etc. |
| DAO Layer | `models/dao/` | Data access objects for all entities |
| Migrations | `models/migrations/` | Versioned schema migrations (001-015) |

### Core Tables

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

### Adding Features

1. Create Blueprint in `routes/new_feature.py`
2. Register in `app.py`: `app.register_blueprint(new_feature_bp)`
3. Add `@require_auth` to protected endpoints
4. Create DAO in `models/dao/new_feature_dao.py` if needed
5. Add migration in `models/migrations/versions/NNN_description.py`
6. Create JS module in `static/js/new_feature.js`
7. Add API module in `static/js/api/new_feature.js`, import in `static/js/api.js`
8. Update `dashboard.html` with UI section

## Commands

| Command | Description |
|---------|-------------|
| `python app.py` | Dev server on port 5001 |
| `flask run` | Alternative (port 5000 by default) |
| `python -m pytest tests/ -v` | Run test suite |
| `docker compose up -d` | Docker deployment (port 5000) |
| `./build_docker.sh build` | Build Docker image |
| `./build_pyinstaller.sh` | Build standalone binary |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Flask secret key |
| `DATABASE_PATH` | `./data/ptvault.db` | SQLite database path |
| `JWT_SECRET_KEY` | Auto-generated | JWT signing key (HS256) |
| `JWT_EXPIRY_HOURS` | `24` | Session token lifetime |
| `ENVIRONMENT` | `development` | `development` or `production` |

Copy `.env.example` to `.env` and customize for production.

## Testing

```bash
python -m pytest tests/ -v
```

- **Unit tests:** `tests/test_nmap_parser.py`, `tests/parsers/` - parser verification
- **DAO tests:** `tests/dao/` - data access object tests
- **Integration tests:** `tests/test_multi_user.py`, `tests/test_rbac.py` - API/auth tests
- **Migration tests:** `tests/test_migrations.py` - schema migration verification
- **Fixtures:** `tests/fixtures/` - sample XML/JSON data for parser tests

## Security

- Argon2id: time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=4, hash_len=32
- JWT (HS256) in httpOnly cookies (XSS protection)
- RBAC: admin, editor, viewer roles with engagement-level access control
- Audit logging for security-sensitive actions
- defusedxml prevents XXE attacks in all XML parsers
- Max upload: 250MB (`Config.MAX_FILE_SIZE`)
- Allowed extensions: `.txt`, `.xml`, `.json`, `.png`, `.jpg`, `.jpeg`, `.pdf`, `.html`, `.log`, `.pcap`, `.nessus`
- Data isolation by engagement_id with team membership checks

## Key Files Reference

| File | Purpose |
|------|---------|
| `features.py` | Blueprint registry (`BLUEPRINTS` list) |
| `app.py:139-187` | Web UI routes (index, setup, dashboard, note editor) |
| `middleware/auth.py:155-192` | `@require_auth` decorator |
| `middleware/auth.py:195-225` | `@require_role` decorator |
| `middleware/auth.py:228-283` | `@require_engagement_access` decorator |
| `models/database.py:33-161` | Database initialization (`init_db`) |
| `models/migrations/manager.py` | Versioned migration runner |
| `models/auth.py:14-20` | Argon2id parameters |
| `models/auth.py:88-108` | JWT token creation |
| `models/schema.sql` | Full schema (19 tables, FTS4, triggers) |
| `utils/parsers/registry.py` | Parser auto-discovery and routing |
| `utils/parsers/base_parser.py` | BaseParser abstract class for all parsers |

## Skills

Claude Code skills are defined in `.claude/skills/` for specialized assistance:

| Skill | Use When |
|-------|----------|
| `sqlite` | Schema design, FTS4, migrations, queries |
| `flask` | Blueprints, routing, middleware, request handling |
| `javascript` | SPA logic, DOM manipulation, API integration |
| `python` | Routes, models, authentication, backend logic |
| `frontend-design` | Tailwind CSS, responsive layouts, dark mode |
| `jwt` | Token generation, validation, session auth |
| `argon2` | Password hashing, verification |
| `tailwind` | Utility-first CSS styling |
| `docker` | Container builds, compose configs |
| `xml-parsing` | Nmap, Nessus, Burp XML parsing |

## Specialized Agents

Agents in `.claude/agents/` for specific workflows:

| Agent | Purpose |
|-------|---------|
| `backend-engineer` | Flask API development, database, parsers |
| `frontend-engineer` | Vanilla JS SPA, API integration |
| `test-engineer` | Unit tests, integration tests |
| `debugger` | Flask routes, SQLite, JWT, parser debugging |
| `designer` | Tailwind CSS, dark mode, responsive layouts |
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
| tailwind | Configures utility-first CSS styling via CDN for responsive component design |
| frontend-design | Applies UI styling with Tailwind CSS CDN, dark mode support, and responsive layouts |
| jwt | Manages JWT token generation, validation, and session authentication in httpOnly cookies |
| argon2 | Implements Argon2id password hashing and verification for user passwords and the database encryption key |


## Skill Usage Guide

When working on tasks involving these technologies, invoke the corresponding skill:

| Skill | Invoke When |
|-------|-------------|
| sqlite | Designs SQLite schema, FTS4 indexes, migrations, and query optimization |
| flask | Configures Flask blueprints, routing, middleware, and request handling patterns |
| tailwind | Configures utility-first CSS styling via CDN for responsive component design |
| python | Manages Flask routes, models, authentication, backend logic, and utility functions |
| jwt | Manages JWT token generation, validation, and session authentication in httpOnly cookies |
| javascript | Handles vanilla JavaScript SPA logic, DOM manipulation, and API integration |
| xml-parsing | Secures XML parsing for Nmap, Nessus, and Burp Suite tool imports |
| frontend-design | Applies UI styling with Tailwind CSS CDN, dark mode support, and responsive layouts |
| docker | Builds Docker images and compose configurations for containerized deployment |
| argon2 | Implements Argon2id password hashing and verification for user passwords and the database encryption key |
| pynacl | Handles cryptographic operations and secure data encryption |
| pytest | Structures unit tests, integration tests, and test fixtures for validation |

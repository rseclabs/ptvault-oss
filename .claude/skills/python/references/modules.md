# Python Modules Reference

## Contents
- Project Module Map
- Blueprint Registration
- DAO Layer
- Parser Registry
- Utility Modules
- Migration System
- WARNING: Circular Imports
- Adding a New Feature Workflow

---

## Project Module Map

```
ptvault/
├── app.py                  # Entry point: 17 Blueprint registrations, teardown
├── config.py               # Config class with env var overrides
├── models/
│   ├── auth.py             # hash_password(), verify_password(), create_session_token()
│   ├── database.py         # get_db_connection(), init_db(), seeding
│   ├── schema.sql          # 19 tables, FTS4, triggers
│   ├── seed_templates.py   # Report template seeding
│   ├── dao/                # 10 DAOs extending BaseDAO
│   └── migrations/         # MigrationManager + 15 version files
├── routes/                 # 17 Flask Blueprints
├── middleware/auth.py      # @require_auth, @require_role, @require_engagement_access
└── utils/
    ├── parsers/            # 11 tool parsers + base + registry
    ├── error_handler.py    # PTVaultError hierarchy, @handle_errors
    ├── pdf_generator.py    # WeasyPrint PDF generation
    ├── attack_map_svg.py   # SVG generation for attack maps
    └── ...                 # See CLAUDE.md for full list
```

---

## Blueprint Registration

All blueprints register in `app.py` lines 98-114:

```python
from routes.auth import auth_bp
from routes.hosts import hosts_bp
from routes.evidence import evidence_bp
# ... 14 more imports

app.register_blueprint(auth_bp)          # /api/auth/*
app.register_blueprint(hosts_bp)         # /api/hosts/*
app.register_blueprint(evidence_bp)      # /api/evidence/*
# ... 14 more registrations
```

### Blueprint naming convention

```python
# File: routes/new_feature.py
# Blueprint name: snake_case matching the module
# Variable name: snake_case with _bp suffix
new_feature_bp = Blueprint('new_feature', __name__, url_prefix='/api/new-feature')
```

URL prefix uses hyphens (`/api/new-feature`), Python uses underscores (`new_feature_bp`).

---

## DAO Layer

10 DAOs in `models/dao/`, all extending `BaseDAO`:

| DAO | Table | Engagement Scoped |
|-----|-------|-------------------|
| `EngagementDAO` | `engagements` | No |
| `EvidenceDAO` | `evidence` | Yes |
| `HostDAO` | `hosts` | Yes |
| `UserDAO` | `users` | No |
| `ReportDAO` | `reports` | Yes |
| `TestPlanDAO` | `test_plans` | Yes |
| `TemplateDAO` | `templates` | No |
| `RelationshipDAO` | `relationships` | Yes |
| `AttackMapDAO` | `attack_maps` | Yes |

### Creating a new DAO

```python
# models/dao/new_feature_dao.py
from models.dao.base import BaseDAO

class NewFeatureDAO(BaseDAO):
    def __init__(self):
        super().__init__('new_features', engagement_scoped=True)

    def find_by_status(self, status: str):
        return self.find_all({'status': status}, order_by='created_at DESC')
```

---

## Parser Registry

`utils/parsers/registry.py` maps tool names to parser classes:

```python
PARSER_REGISTRY = {
    'nmap': NmapToolParser,
    'burp': BurpToolParser,
    'burp_suite': BurpToolParser,   # Alias
    'nessus': NessusToolParser,
    'zap': ZAPParser,
    'nuclei': NucleiParser,
    'metasploit': MetasploitParser,
    'msf': MetasploitParser,        # Alias
    # ... 4 more
}

def get_parser(tool_name: str, file_path: str) -> Optional[BaseToolParser]:
    parser_class = PARSER_REGISTRY.get(tool_name.lower().strip())
    if not parser_class:
        raise ValueError(f"Unknown tool: {tool_name}")
    return parser_class(file_path)

def detect_parser(file_path: str) -> Optional[BaseToolParser]:
    """Try each parser's validate() in priority order."""
    for tool_name in detection_order:
        parser = PARSER_REGISTRY[tool_name](file_path)
        if parser.validate():
            return parser
    return None
```

See the **xml-parsing** skill for implementing new parsers.

---

## Utility Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `error_handler.py` | Exception classes + decorator | `PTVaultError`, `@handle_errors`, `require_fields()` |
| `pdf_generator.py` | WeasyPrint PDF export | `generate_pdf(html_content)` |
| `attack_map_svg.py` | SVG for attack maps | `generate_attack_map_svg(nodes, edges)` |
| `report_auto_populator.py` | Auto-fill reports | `auto_populate(report_id)` |
| `template_renderer.py` | Jinja2 report templates | `render_template(template, data)` |
| `file_helpers.py` | File utilities | `sanitize_filename()`, `allowed_file()` |
| `host_extractor.py` | IP/hostname extraction | `extract_hosts(text)` |
| `audit_logger.py` | Compliance audit trail | `log_action(user, action, details)` |

---

## Migration System

Versioned migrations in `models/migrations/`:

```python
# models/migrations/versions/016_add_new_table.py
def upgrade(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS new_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engagement_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (engagement_id) REFERENCES engagements(id)
        )
    ''')
    conn.commit()

def downgrade(conn):
    conn.execute('DROP TABLE IF EXISTS new_features')
    conn.commit()
```

`MigrationManager` in `models/migrations/manager.py` runs pending migrations on first authenticated request. See the **sqlite** skill for schema patterns.

---

## WARNING: Circular Imports

```python
# BAD - routes/hosts.py imports from routes/evidence.py
from routes.evidence import parse_evidence  # Circular!

# GOOD - Move shared code to utils/
from utils.evidence_helpers import parse_evidence

# GOOD - Delayed import when unavoidable
def some_function():
    from models.database import migrate_host_indicators
    migrate_host_indicators(cursor)
```

**Why:** Flask Blueprints importing from each other creates import cycles. The `utils/` package exists specifically for shared logic.

---

## Adding a New Feature Workflow

```
- [ ] Step 1: Create migration in `models/migrations/versions/NNN_description.py`
- [ ] Step 2: Create DAO in `models/dao/new_feature_dao.py`
- [ ] Step 3: Create Blueprint in `routes/new_feature.py`
- [ ] Step 4: Import and register Blueprint in `app.py`
- [ ] Step 5: Add `@require_auth` to all protected endpoints
- [ ] Step 6: Create JS API module in `static/js/api/new_feature.js`
- [ ] Step 7: Import new API module in `static/js/api.js`
- [ ] Step 8: Create UI module in `static/js/new_feature.js`
- [ ] Step 9: Add UI section to `templates/dashboard.html`
- [ ] Step 10: Validate: `python -m pytest tests/ -v`
```

1. Make changes
2. Validate: `python -m pytest tests/ -v`
3. If tests fail, fix issues and repeat step 2
4. Only proceed when all tests pass

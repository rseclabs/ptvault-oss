# PTVault Quick Start Guide

## Prerequisites

- Python 3.10+ (`python3 --version`)
- Linux, macOS or Windows. Database encryption uses the `sqlcipher3` package from `requirements.txt`, which ships prebuilt wheels with SQLCipher included, so no system SQLCipher packages are needed.
- Optional, for server-side PDF export: the Pango library (`sudo apt install libpango-1.0-0 libpangoft2-1.0-0` on Debian/Ubuntu/Kali, `brew install pango` on macOS). Without it, PDF export falls back to the browser's print dialog.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

## Running PTVault

```bash
python3 app.py                # http://localhost:5001
python3 app.py -i 0.0.0.0 -p 8080   # custom interface/port
```

The database (`data/ptvault.db`) is created and migrated automatically on first start.

## First-Time Setup

Open **http://localhost:5001** — you are redirected to the setup wizard to create the initial admin account. To do the same from the command line:

### 1. Get a CSRF token

All mutating API requests use a double-submit CSRF token: the `csrf_token` cookie must be echoed in an `X-CSRF-Token` header.

```bash
curl -s -c cookies.txt http://localhost:5001/api/auth/csrf-token > /dev/null
CSRF=$(awk '$6 == "csrf_token" {print $7}' cookies.txt)
```

### 2. Create the admin account

```bash
curl -b cookies.txt -c cookies.txt -X POST http://localhost:5001/api/auth/setup \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"email":"admin@example.com","password":"YourSecurePassword123!","full_name":"Admin"}'
```

### 3. Log in

```bash
curl -b cookies.txt -c cookies.txt -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"email":"admin@example.com","password":"YourSecurePassword123!"}'
CSRF=$(awk '$6 == "csrf_token" {print $7}' cookies.txt)   # token may rotate on login
```

The session cookie is now saved in `cookies.txt`. Every POST/PUT/DELETE below also sends `-H "X-CSRF-Token: $CSRF"`.

## Basic Testing Workflow

### 4. Create an Engagement

```bash
curl -b cookies.txt -X POST http://localhost:5001/api/engagements \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ACME Corp Pentest",
    "client": "ACME Corporation",
    "start_date": "2025-12-01",
    "end_date": "2025-12-15",
    "status": "active",
    "scope": "External network penetration test",
    "contact_name": "John Smith",
    "contact_email": "john.smith@acme.com",
    "notes": "Q4 2025 security assessment"
  }'
```

Expected response:
```json
{
  "id": 1,
  "name": "ACME Corp Pentest",
  "client": "ACME Corporation",
  ...
}
```

### 5. Set Active Engagement

```bash
curl -b cookies.txt -c cookies.txt -X POST http://localhost:5001/api/engagements/active \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{"engagement_id": 1}'
```

### 6. Add Evidence

```bash
# Add a note
curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_type": "note",
    "title": "SQL Injection in Login Form",
    "content": "Found SQL injection vulnerability in /admin/login endpoint. Payload: '\'' OR '\''1'\''='\''1 bypasses authentication.",
    "tags": "critical,sql-injection,authentication"
  }'

# Add command output
curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_type": "command_output",
    "title": "Nmap Scan Results",
    "content": "PORT     STATE SERVICE\n22/tcp   open  ssh\n80/tcp   open  http\n443/tcp  open  https\n3306/tcp open  mysql",
    "tags": "nmap,reconnaissance,high",
    "metadata": "{\"tool\":\"nmap\"}"
  }'

# Upload a file (screenshot or tool output)
curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -F "evidence_type=screenshot" \
  -F "title=Admin Panel Access" \
  -F "content=Successfully accessed admin panel without authentication" \
  -F "tags=critical,authentication-bypass" \
  -F "file=@/path/to/screenshot.png"
```

### 7. Search Evidence

```bash
# Search by keyword
curl -b cookies.txt "http://localhost:5001/api/evidence/search?q=sql+injection"

# Filter by tag (comma-separated tags must all match; use tags_any= for OR)
curl -b cookies.txt "http://localhost:5001/api/evidence/filter?tags=critical"

# Filter by severity (derived from parsed scanner results such as Nessus)
curl -b cookies.txt "http://localhost:5001/api/evidence/filter?severity=critical"

# Filter by tool
curl -b cookies.txt "http://localhost:5001/api/evidence/filter?tool=nmap"

# Combined filters
curl -b cookies.txt "http://localhost:5001/api/evidence/filter?type=note&tags=critical"
```

### 8. Export Engagement Data

```bash
# Export to JSON
curl -b cookies.txt http://localhost:5001/api/engagements/1/export/json \
  -o acme-export.json

# Export to Markdown
curl -b cookies.txt http://localhost:5001/api/engagements/1/export/markdown \
  -o acme-report.md

# List available templates
curl -b cookies.txt http://localhost:5001/api/templates

# Export using template
curl -b cookies.txt http://localhost:5001/api/engagements/1/export/template/default \
  -o acme-report-default.md

curl -b cookies.txt http://localhost:5001/api/engagements/1/export/template/executive \
  -o acme-report-executive.md
```

## Advanced: Tool Integration

### Upload nmap XML

```bash
# Upload nmap scan results
curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -F "evidence_type=tool_output" \
  -F "title=Complete Network Scan" \
  -F "content=Full network scan results" \
  -F "tags=nmap,scan" \
  -F "file=@/path/to/nmap-scan.xml"
```

PTVault will automatically:
- Detect it's an nmap XML file
- Parse hosts, ports, services, and OS detection
- Extract structured metadata
- Auto-tag with tool type and findings

### Upload Burp Suite Results

```bash
curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -F "evidence_type=tool_output" \
  -F "title=Web Application Scan" \
  -F "content=Burp Suite findings" \
  -F "tags=burp,web" \
  -F "file=@/path/to/burp-export.xml"
```

### Upload Nessus Scan

```bash
curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -F "evidence_type=tool_output" \
  -F "title=Vulnerability Scan" \
  -F "content=Nessus scan results" \
  -F "tags=nessus,scan" \
  -F "file=@/path/to/nessus-scan.nessus"
```

## Testing the Search System

```bash
# Create diverse evidence
curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_type": "note",
    "title": "XSS in Contact Form",
    "content": "Reflected XSS vulnerability found in contact form",
    "tags": "medium,xss,web"
  }'

curl -b cookies.txt -X POST http://localhost:5001/api/evidence \
  -H "X-CSRF-Token: $CSRF" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_type": "note",
    "title": "Weak Password Policy",
    "content": "No complexity requirements, allows password123",
    "tags": "low,password,policy"
  }'

# Test full-text search
curl -b cookies.txt "http://localhost:5001/api/evidence/search?q=password"

# Test tag autocomplete
curl -b cookies.txt "http://localhost:5001/api/tags/autocomplete?q=cr"
# Returns tags used in the active engagement, e.g. {"suggestions": [{"name": "critical", "count": 2}]}

# Test filtering by multiple tags (AND logic)
curl -b cookies.txt "http://localhost:5001/api/evidence/filter?tags=critical,sql-injection"
```

## Viewing Your Data

### List All Engagements

```bash
curl -b cookies.txt http://localhost:5001/api/engagements | python3 -m json.tool
```

### List All Evidence for Active Engagement

```bash
curl -b cookies.txt http://localhost:5001/api/evidence | python3 -m json.tool
```

### Get Engagement Statistics

```bash
# This is included in JSON export
curl -b cookies.txt http://localhost:5001/api/engagements/1/export/json | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data['statistics'], indent=2))"
```

## Troubleshooting

### Database Issues

```bash
# Start over with an empty database (WARNING: deletes all data!)
# Stop PTVault first. If encryption is enabled, the key and salt must go too.
rm -f ./data/ptvault.db* ./data/encryption.key ./data/encryption.salt
python3 app.py   # recreates and migrates the database, then run setup again
```

### Permission Errors

```bash
chmod 755 data/ data/uploads/
```

### Encryption Not Available

```bash
# PTVault logs "SQLCipher encryption: DISABLED" when the driver is missing
python3 -c "import sqlcipher3; print('OK')"
pip install -r requirements.txt   # installs sqlcipher3
```

### Port Already in Use

```bash
python3 app.py -p 5002
```

## Security Notes

- **Encryption files**: Back up `data/encryption.key` and `data/encryption.salt` with the database — an encrypted database cannot be opened without them
- **Local Only**: PTVault is designed for local or trusted-network use; put it behind HTTPS if it is reachable by others
- **Engagement Isolation**: Users only see engagements they own or are a member of; admins see all
- **Encryption**: The database is encrypted at rest with SQLCipher when `sqlcipher3` is installed
- **Sessions**: JWT tokens in httpOnly cookies (XSS protection)

## Next Steps

1. **Create real engagements** with your actual pentest data
2. **Upload tool outputs** (nmap, Burp, Nessus) to test parsers
3. **Test search** with various queries and filters
4. **Generate reports** using templates
5. **Customize templates** in `templates/reports/` for your report style

## API Reference

For complete API documentation, see the implementation:
- Auth: `routes/auth.py`
- Engagements: `routes/engagements.py`
- Evidence: `routes/evidence.py`
- Tags: `routes/tags.py`
- Templates: `routes/templates.py`

## Getting Help

- Check `README.md` for detailed setup instructions
- Browse the user documentation in [`docs/`](docs/README.md)
- Report bugs or ask questions via GitHub Issues

---

**PTVault v1.0** - Secure Evidence Management for Penetration Testers

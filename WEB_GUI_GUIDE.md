# PTVault Web GUI - User Guide

## 🎉 PTVault Now Has a Web Interface!

Your PTVault installation now includes a modern, professional web GUI for managing penetration testing evidence.

---

## Quick Start

### 1. Start PTVault

```bash
# Stop any old instances
pkill -f "python.*app.py"

# Start fresh
python3 app.py
```

Or use the startup script:
```bash
./start_ptvault.sh
```

### 2. Open Your Browser

Navigate to: **http://localhost:5000**

### 3. First-Time Setup

On first visit, you'll be redirected to the setup page:

1. Create a strong master password (minimum 8 characters)
2. Confirm the password
3. Click "Create & Unlock"

**⚠️ IMPORTANT:** Your master password encrypts all data. **Store it securely!** If lost, your data cannot be recovered.

### 4. Login

After setup, you'll see the login page:

1. Enter your master password
2. Click "Unlock PTVault"
3. You're in!

---

## Features

### Dashboard Overview

**Left Sidebar:**
- **Engagements List** - All your client projects
- **Evidence Stats** - Count by severity (Critical, High, Medium, Low)
- **+ Button** - Create new engagement

**Main Area:**
- **Evidence List** - All findings for active engagement
- **Search Bar** - Real-time full-text search
- **Filter Chips** - Quick filters by tag/severity
- **+ New Evidence** - Quick capture button
- **Export** - Download reports

**Top Bar:**
- **Active Engagement** - Shows which project you're working on
- **Theme Toggle** (🌙/☀️) - Switch between dark/light mode
- **Logout** - End session

### Creating an Engagement

1. Click **+ Button** in sidebar
2. Fill in details:
   - **Name** (required) - e.g., "ACME Corp Pentest"
   - **Client** - e.g., "ACME Corporation"
   - **Dates** - Start and end dates
   - **Status** - Active/Completed/Archived
   - **Scope** - What you're testing
   - **Contact** - Name and email
   - **Notes** - Additional info
3. Click **Create Engagement**
4. Engagement appears in sidebar (click to make active)

### Adding Evidence

1. Make sure an engagement is active (shown in top bar)
2. Click **+ New Evidence** button
3. Choose **Type:**
   - **Note** - Written observations
   - **Screenshot** - Image file
   - **Command Output** - Terminal output
   - **Tool Output** - nmap/Burp/Nessus files
   - **Other** - Anything else
4. Fill in:
   - **Title** - Brief description
   - **Content** - Detailed findings
   - **Tags** - Comma-separated (e.g., critical,sql-injection,auth)
   - **Severity** - Critical/High/Medium/Low
   - **Attachment** - Optional file upload
5. Click **Add Evidence**

### Search & Filter

**Search:**
- Type in search box for instant results
- Searches titles, content, and tags
- Real-time as you type

**Filter by Severity:**
- Click severity chips (🔴 Critical, 🟠 High, etc.)
- Multiple selections work together (AND logic)

**Filter by Tags:**
- Click any tag in evidence cards
- Shows only evidence with that tag

**Clear Filters:**
- Click "Clear Filters" button to reset

### Exporting Data

1. Click **Export** button (⬇)
2. Choose format:
   - **JSON** - Complete data dump (for automation)
   - **Markdown** - Formatted report
   - **Template: Default** - Comprehensive report
   - **Template: Executive** - Summary for leadership
   - **Template: Findings** - Technical details
3. File downloads automatically

---

## Keyboard Shortcuts

- **Ctrl+N** - New evidence (quick capture)
- **Ctrl+F** - Focus search bar
- **Ctrl+E** - Open export dialog
- **Esc** - Close any open modal

---

## Tips & Tricks

### Evidence Organization

**Use consistent tags:**
- Severity: `critical`, `high`, `medium`, `low`
- Category: `sql-injection`, `xss`, `auth-bypass`, `rce`
- System: `web`, `network`, `api`, `mobile`
- Tool: `nmap`, `burp`, `nessus`, `manual`

**Example tagging:**
```
critical,sql-injection,web,burp
high,rce,api,manual
medium,xss,web,burp
```

### Tool Output Upload

When uploading tool outputs:

1. **nmap XML:**
   - Choose type: Tool Output
   - Upload your .xml file
   - PTVault auto-parses hosts, ports, services
   - Auto-tags with "nmap"

2. **Burp Suite:**
   - Export as XML from Burp
   - Upload as Tool Output
   - Auto-parses findings
   - Auto-tags with "burp"

3. **Nessus:**
   - Export .nessus file
   - Upload as Tool Output
   - Auto-parses vulnerabilities
   - Filters severity >= Low
   - Auto-tags with "nessus"

### Dark Mode

- **Toggle:** Click 🌙/☀️ icon in top-right
- **Default:** Dark mode (easier on eyes during long engagements)
- **Preference saved:** Persists between sessions

### Multiple Engagements

- Create separate engagements for each client
- Only one engagement active at a time
- Switch by clicking engagement in sidebar
- Data completely isolated between engagements

### Session Management

- Session stays active for security
- Logout when done for the day
- Auto-redirect to login if session expires

---

## Customizing Report Templates

Templates are located in: `templates/reports/`

**Available templates:**
- `default.md` - Comprehensive report with all sections
- `executive.md` - Executive summary for leadership
- `findings.md` - Technical findings with CVE-style IDs

**To customize:**

1. Edit the template file (Markdown + Jinja2)
2. Available variables:
   ```jinja2
   {{ engagement.name }}
   {{ engagement.client }}
   {{ engagement.start_date }}
   {{ statistics.total_evidence }}
   {{ statistics.evidence_by_severity.critical }}
   {% for evidence in critical_findings %}
     {{ evidence.title }}
     {{ evidence.content }}
   {% endfor %}
   ```
3. Save and use in exports

---

## Troubleshooting

### Can't Access Web Interface

```bash
# Check if Flask is running
ps aux | grep "python.*app.py"

# Check what's on port 5000
lsof -i :5000

# Restart cleanly
pkill -f "python.*app.py"
./start_ptvault.sh
```

### "404 Not Found" Errors

- Make sure you're accessing `http://localhost:5000` (not /api/...)
- Check Flask started successfully: `tail flask.log`
- Restart Flask if needed

### Session/Login Issues

- Clear browser cookies for localhost:5000
- Try incognito/private window
- Check browser console for errors (F12)

### Database Issues

```bash
# Reset database (WARNING: deletes all data!)
rm -f ./data/ptvault.db*
python3 -c "from models.database import init_db; init_db()"

# Restart PTVault
./start_ptvault.sh
```

### Static Files Not Loading

- CSS/JS files in `static/` directory
- Flask serves them automatically at `/static/`
- Check browser console (F12) for 404s
- Verify files exist: `ls static/css/ static/js/`

---

## Technical Details

### Architecture

- **Backend:** Flask (Python 3.10+)
- **Database:** SQLCipher (encrypted SQLite)
- **Frontend:** Vanilla JavaScript (ES6+)
- **Styling:** Custom CSS with CSS variables
- **No external dependencies:** Everything self-contained

### File Structure

```
ptvault/
├── app.py                    # Flask application
├── static/
│   ├── css/
│   │   └── main.css         # Styles (22KB)
│   └── js/
│       ├── api.js           # API wrapper (17KB)
│       ├── auth.js          # Authentication (5KB)
│       ├── app.js           # Main dashboard (14KB)
│       └── utils.js         # Utilities (10KB)
├── templates/
│   ├── login.html           # Login page
│   ├── setup.html           # Setup page
│   ├── dashboard.html       # Main app
│   └── reports/             # Export templates
└── data/
    ├── ptvault.db           # Encrypted database
    └── uploads/             # Evidence files
```

### Security

- **Encryption:** All data encrypted at rest (SQLCipher)
- **Authentication:** JWT tokens in httpOnly cookies (XSS protection)
- **Session:** Server-side session management
- **CSRF:** Protected via session cookies
- **Input Validation:** Client-side and server-side
- **File Upload:** Whitelist extensions, size limits, sanitization
- **XSS Prevention:** HTML escaping in JavaScript

### Browser Compatibility

- **Chrome/Edge:** ✅ Full support
- **Firefox:** ✅ Full support
- **Safari:** ✅ Full support
- **Mobile:** ✅ Responsive (works on tablets)

**Minimum versions:**
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

---

## API Integration

The GUI is built on top of the existing REST API. You can still use the API directly:

```bash
# Login
curl -c cookies.txt -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"master_password":"YourPassword"}'

# Create engagement
curl -b cookies.txt -X POST http://localhost:5000/api/engagements \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Engagement",...}'

# Search evidence
curl -b cookies.txt "http://localhost:5000/api/evidence/search?q=sql"
```

See `QUICKSTART.md` for complete API documentation.

---

## What's Next?

1. **Create your first engagement**
2. **Add some evidence** with different severity levels
3. **Upload tool outputs** (nmap, Burp, Nessus)
4. **Test search and filtering**
5. **Export a report** using templates
6. **Customize templates** for your reporting style
7. **Use keyboard shortcuts** for faster workflow

---

**PTVault v1.0** - Now with a professional web interface!
Built for penetration testers, by penetration testers.

Questions? Check `README.md` or `QUICKSTART.md` for more details.

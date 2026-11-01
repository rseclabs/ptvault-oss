import os
import sys
import logging
from dotenv import load_dotenv

# When running as PyInstaller bundle, look for .env next to the executable
if getattr(sys, 'frozen', False):
    _runtime_dir = os.path.dirname(sys.executable)
    load_dotenv(os.path.join(_runtime_dir, '.env'))
else:
    load_dotenv()

from flask import Flask, jsonify, g, render_template, redirect, url_for, request
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('ENVIRONMENT', 'development') == 'development' else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ptvault')

from models.database import init_db, get_db_connection, run_migrations
from models.encryption import is_encryption_available, is_encryption_enabled, check_and_migrate_if_needed
from features import register_blueprints
from config import BASE_DIR

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config.from_object(Config)

# Set Flask's max content length to match our file size limit
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE

# Rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"],
    storage_uri="memory://",
)

# Register blueprints
register_blueprints(app)

# Apply specific rate limits to auth endpoints
limiter.limit("5 per minute")(app.view_functions['auth.login'])
limiter.limit("3 per minute")(app.view_functions['auth.setup'])

# Encryption status check
if is_encryption_available():
    if is_encryption_enabled():
        check_and_migrate_if_needed(Config.DATABASE_PATH)
        logger.info("SQLCipher encryption: ENABLED")
    else:
        logger.info("SQLCipher available but not yet configured (run setup)")
else:
    logger.info("SQLCipher encryption: DISABLED (pysqlcipher3 not installed)")

if Config.ENCRYPTION_REQUIRED and not is_encryption_available():
    logger.critical("PTVAULT_ENCRYPTION_REQUIRED=true but pysqlcipher3 not installed")
    sys.exit(1)

# Initialize database on first run
if not os.path.exists(Config.DATABASE_PATH):
    init_db()
else:
    # Run migrations on existing database
    try:
        run_migrations()
        logger.info("Database migrations completed")
    except Exception as e:
        logger.warning("Migration check completed - %s", e)

# Teardown: close database connection after each request
@app.teardown_appcontext
def close_db(error):
    """Close database connection if it exists."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.before_request
def csrf_protect():
    """Validate CSRF token on mutating requests (double-submit cookie pattern)."""
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return  # Safe methods don't need CSRF

    # Skip CSRF for setup and login (no session yet)
    if request.path in ('/api/auth/setup', '/api/auth/login', '/api/auth/csrf-token'):
        return

    # Skip CSRF for non-API routes
    if not request.path.startswith('/api/'):
        return

    cookie_token = request.cookies.get('csrf_token')
    header_token = request.headers.get('X-CSRF-Token')

    if not cookie_token or not header_token:
        app.logger.warning('CSRF missing — path=%s cookie_present=%s header_present=%s',
                           request.path, bool(cookie_token), bool(header_token))
        return jsonify({"error": "CSRF token missing"}), 403

    if cookie_token != header_token:
        return jsonify({"error": "CSRF token mismatch"}), 403


@app.after_request
def set_security_headers(response):
    """Add security headers to all responses."""
    # Disable caching for JS/CSS in dev so changes take effect on normal reload
    if Config.ENVIRONMENT != 'production' and request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-store'

    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # CyberChef requires relaxed CSP (blob: workers, data: URIs, eval for recipes)
    if request.path.startswith('/api/admin/cyberchef'):
        csp = (
            "default-src 'self' blob: data:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: data:; "
            "style-src 'self' 'unsafe-inline' blob: data:; "
            "worker-src 'self' blob:; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' blob: data:; "
            "font-src 'self' data: blob:; "
            "frame-src 'none'"
        )
    else:
        # Content Security Policy - allow Tailwind CDN and Lucide CDN
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://d3js.org https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-src 'self' https://gchq.github.io"
        )
    response.headers['Content-Security-Policy'] = csp

    # HSTS only in production
    if Config.ENVIRONMENT == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response

# ============================================
# WEB UI ROUTES
# ============================================

@app.route('/', methods=['GET'])
def index():
    """
    Root route - check if setup is needed, redirect to login or setup page.
    """
    # Check if database file exists and has data (indicates setup was completed)
    # We can't query the encrypted database without the user's password-derived key
    db_path = Config.DATABASE_PATH
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        # Database exists with data, show login page
        return render_template('login.html')
    else:
        # No database, redirect to setup
        return redirect(url_for('setup'))

@app.route('/login', methods=['GET'])
def login():
    """Redirect /login to root (which handles login/setup flow)."""
    return redirect(url_for('index'))

@app.route('/setup', methods=['GET'])
def setup():
    """Setup page for first-time configuration."""
    return render_template('setup.html')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """
    Dashboard page - requires authentication via session cookie.
    """
    # Check if user has valid auth token cookie
    auth_token = request.cookies.get('auth_token')

    if not auth_token:
        # No session, redirect to login
        return redirect(url_for('index'))

    # Session exists, show dashboard
    return render_template('dashboard.html')

@app.route('/note/new', methods=['GET'])
def note_editor():
    """
    Note editor page - requires authentication via session cookie.
    """
    # Check if user has valid auth token cookie
    auth_token = request.cookies.get('auth_token')

    if not auth_token:
        # No session, redirect to login
        return redirect(url_for('index'))

    # Session exists, show note editor
    return render_template('note_editor.html')


@app.route('/finding/new', methods=['GET'])
def finding_editor():
    """
    Finding editor page - requires authentication via session cookie.
    """
    auth_token = request.cookies.get('auth_token')

    if not auth_token:
        return redirect(url_for('index'))

    return render_template('finding_editor.html')

# ============================================
# API HEALTH CHECK ROUTES
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})

@app.route('/db-status', methods=['GET'])
def db_status():
    """Database status endpoint."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM engagements")
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({"status": "ok", "engagements_count": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    import argparse
    is_frozen = getattr(sys, 'frozen', False)
    parser = argparse.ArgumentParser(description='PTVault server')
    parser.add_argument('-i', '--interface', default='localhost',
                        help='IP address or hostname to bind to (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=5001,
                        help='Port to listen on (default: 5001)')
    args = parser.parse_args()
    app.run(
        host=args.interface,
        port=args.port,
        debug=not is_frozen,
        use_reloader=not is_frozen,
    )

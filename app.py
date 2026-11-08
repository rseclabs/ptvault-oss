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
from utils.security_headers import apply_security_headers

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('ENVIRONMENT', 'development') == 'development' else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ptvault')

# Validate or load the signing secrets before anything else: a placeholder
# key lets anyone forge a session, so refuse to start.
from config import InsecureSecretError, debugger_allowed, load_secrets
try:
    load_secrets()
except InsecureSecretError as e:
    logger.critical("Refusing to start: %s", e)
    sys.exit(1)

from models.database import init_db, get_db_connection, run_migrations, setup_required
from models.encryption import (auto_unlock_from_env, check_and_migrate_if_needed, is_encryption_available,
                               is_encryption_enabled, is_locked, plaintext_database_refusal,
                               retire_stray_key_file)
from features import register_blueprints
from middleware.auth import require_auth, require_role
from utils.csrf import csrf_protect
from utils.rate_limits import configure_rate_limits
from config import BASE_DIR

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config.from_object(Config)

# Set Flask's max content length to match our file size limit
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE

# Register blueprints
register_blueprints(app)

# Rate limits: default, login, setup and password changes; storage and proxy
# handling from the environment (utils/rate_limits.py, L-8)
limiter = configure_rate_limits(app)

# Encryption status check. The key is held in memory only (M-8): an encrypted
# database stays locked until /unlock is given the database passphrase, unless
# PTVAULT_DB_PASSPHRASE (or the PTVAULT_STORE_KEY_FILE opt-in) provides it.
if is_encryption_available():
    retire_stray_key_file()      # a key file from an older version with no encrypted database (L-15)
    auto_unlock_from_env()
    if is_locked():
        logger.warning("Database is encrypted and locked: open /unlock and enter the database passphrase")
    elif is_encryption_enabled():
        check_and_migrate_if_needed(Config.DATABASE_PATH)
        logger.info("SQLCipher encryption: ENABLED")
    else:
        logger.info("SQLCipher available but not yet configured (run setup)")
else:
    logger.info("SQLCipher encryption: DISABLED (sqlcipher3 not installed)")

if Config.ENCRYPTION_REQUIRED and not is_encryption_available():
    logger.critical("Encryption is required (PTVAULT_ENCRYPTION_REQUIRED, on by default) but sqlcipher3 "
                    "is not installed. Install requirements, or set PTVAULT_ENCRYPTION_REQUIRED=0.")
    sys.exit(1)

# A plaintext database that setup has already used is refused while encryption
# is required: the data on disk would be unprotected (M-11).
_refusal = plaintext_database_refusal(Config.DATABASE_PATH)
if _refusal:
    logger.critical(_refusal)
    sys.exit(1)

# Initialize database on first run
if not os.path.exists(Config.DATABASE_PATH):
    init_db()
elif is_locked():
    logger.info("Migrations will run when the database is unlocked")
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

# CSRF on every mutating API request, login and setup included (utils/csrf.py, L-8)
app.before_request(csrf_protect)


@app.after_request
def set_security_headers(response):
    """Add security headers to all responses (utils/security_headers.py)."""
    return apply_security_headers(response)

# ============================================
# WEB UI ROUTES
# ============================================

@app.route('/', methods=['GET'])
def index():
    """
    Root route - the setup wizard until an account exists, then the login page.
    """
    if setup_required():
        return redirect(url_for('setup'))
    return render_template('login.html')

@app.route('/login', methods=['GET'])
def login():
    """Redirect /login to root (which handles login/setup flow)."""
    return redirect(url_for('index'))

@app.route('/setup', methods=['GET'])
def setup():
    """Setup page for first-time configuration; once an account exists, go to login."""
    if not setup_required():
        return redirect(url_for('index'))
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
@require_auth
@require_role('admin')
def db_status():
    """Database status endpoint (admins only, L-3)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM engagements")
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({"status": "ok", "engagements_count": count})
    except Exception:
        logger.exception("Database status check failed")
        return jsonify({"status": "error", "message": "database unavailable"}), 500

if __name__ == '__main__':
    import argparse
    is_frozen = getattr(sys, 'frozen', False)
    parser = argparse.ArgumentParser(description='PTVault server')
    parser.add_argument('-i', '--interface', default='localhost',
                        help='IP address or hostname to bind to (default: localhost)')
    parser.add_argument('-p', '--port', type=int, default=5001,
                        help='Port to listen on (default: 5001)')
    parser.add_argument('--debug', action='store_true',
                        help='Werkzeug debugger and auto-reload (loopback, non-production only; '
                             'or set PTVAULT_DEBUG=1)')
    args = parser.parse_args()
    # The Werkzeug debugger executes code typed into the browser, so it is off
    # unless asked for, and never in production or on a reachable interface (L-10).
    debug = debugger_allowed(args.debug or Config.DEBUG, args.interface, Config.ENVIRONMENT, is_frozen)
    if (args.debug or Config.DEBUG) and not debug:
        logger.warning("Debug mode refused (production, frozen build or non-loopback interface)")
    app.run(
        host=args.interface,
        port=args.port,
        debug=debug,
        use_reloader=debug,
    )

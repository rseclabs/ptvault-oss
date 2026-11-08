"""Admin panel routes for PTVault."""

from flask import Blueprint, request, jsonify, g, send_from_directory, redirect
from middleware.auth import require_auth, require_role
from models.auth import revoke_all_sessions
from utils.audit_logger import AuditLogger
from utils.error_handler import handle_errors, internal_error, validate_password_strength
from utils.security_headers import CYBERCHEF_CSP
import logging
import os
import json
import zipfile
import requests
import shutil
import hashlib
import tempfile
import threading
from datetime import datetime, timezone

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')
logger = logging.getLogger(__name__)

# Simple cache for idle timeout setting (shared with middleware)
# Keys: 'value' (int minutes), 'expires' (timestamp)
_idle_timeout_cache = {}

import time

def get_idle_timeout_minutes(conn):
    """Get idle timeout from settings with 60-second cache."""
    now = time.time()
    if _idle_timeout_cache.get('expires', 0) > now:
        return _idle_timeout_cache['value']

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'idle_timeout_minutes'")
        row = cursor.fetchone()
        val = int(row[0]) if row else 15
    except Exception:
        val = 15

    _idle_timeout_cache['value'] = val
    _idle_timeout_cache['expires'] = now + 60
    return val

# Configuration
from config import BASE_DIR, RUNTIME_DIR
STATIC_DIR = os.path.join(BASE_DIR, 'static')
# CyberChef is downloaded at runtime, so it needs a writable location
TOOLS_DIR = os.path.join(RUNTIME_DIR, 'static', 'tools')
CYBERCHEF_DIR = os.path.join(TOOLS_DIR, 'cyberchef')
CYBERCHEF_VERSION_FILE = os.path.join(CYBERCHEF_DIR, 'version.json')
# One pinned release (M-5): never "latest". To update, pick a release that has
# been public for at least two weeks, check GitHub's published sha256 digest for
# the asset, download it, confirm the hash locally, and change all three values.
CYBERCHEF_VERSION = 'v11.5.0'
CYBERCHEF_URL = ('https://github.com/gchq/CyberChef/releases/download/v11.5.0/'
                 'CyberChef_8cd426dd4f40f1423912d5fad91b578a86a65112.zip')
CYBERCHEF_SHA256 = 'f6478925d3eaa16ec08626a85f5b85eed10d531a5e18700615fed7ecb024cccf'
CYBERCHEF_MAX_BYTES = 150 * 1024 * 1024
_cyberchef_install_lock = threading.Lock()

# CyberChef needs unsafe-eval, so its pages run sandboxed: an opaque origin that
# cannot read PTVault's cookies or call the API with the user's session. Its
# files are the public release files, so they are served without a login (the
# sandboxed page's own requests carry no session); the page itself needs one.
CYBERCHEF_PAGE_CSP = CYBERCHEF_CSP + "; sandbox allow-scripts allow-popups allow-downloads allow-modals allow-forms"


class CyberChefInstallError(Exception):
    """The pinned download could not be fetched, verified or unpacked."""


def get_cyberchef_version():
    """Read installed CyberChef version from version.json."""
    if not os.path.exists(CYBERCHEF_VERSION_FILE):
        return None
    try:
        with open(CYBERCHEF_VERSION_FILE, 'r') as f:
            data = json.load(f)
            return data.get('version')
    except Exception:
        return None


def save_cyberchef_version(version):
    """Save CyberChef version to version.json."""
    data = {
        'version': version,
        'installed_at': datetime.now(timezone.utc).isoformat(),
        'source': 'github'
    }
    with open(CYBERCHEF_VERSION_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def is_cyberchef_installed():
    """Check if CyberChef is installed by looking for any CyberChef*.html file."""
    if not os.path.exists(CYBERCHEF_DIR):
        return False
    for f in os.listdir(CYBERCHEF_DIR):
        if f.startswith('CyberChef') and f.endswith('.html'):
            return True
    return False


@admin_bp.route('/cyberchef/status', methods=['GET'])
@require_auth
@handle_errors
def cyberchef_status():
    """Get CyberChef installation status."""
    installed = is_cyberchef_installed()
    version = get_cyberchef_version()

    result = {
        'installed': installed,
        'version': version
    }

    if os.path.exists(CYBERCHEF_VERSION_FILE):
        try:
            with open(CYBERCHEF_VERSION_FILE, 'r') as f:
                data = json.load(f)
                result['installed_at'] = data.get('installed_at')
        except Exception:
            pass

    return jsonify(result), 200


@admin_bp.route('/cyberchef/check-update', methods=['GET'])
@require_auth
@require_role('admin')
@handle_errors
def check_cyberchef_update():
    """Report the installed CyberChef version against the pinned one (no network call)."""
    current_version = get_cyberchef_version()
    return jsonify({
        'current_version': current_version,
        'latest_version': CYBERCHEF_VERSION,
        'update_available': current_version != CYBERCHEF_VERSION,
        'download_url': CYBERCHEF_URL,
    }), 200


def _download_pinned_cyberchef(zip_path):
    """Download the pinned asset to zip_path, enforcing the size cap and SHA-256."""
    digest = hashlib.sha256()
    size = 0
    response = requests.get(CYBERCHEF_URL, stream=True, timeout=(10, 120))
    response.raise_for_status()
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > CYBERCHEF_MAX_BYTES:
                raise CyberChefInstallError('download is larger than expected')
            digest.update(chunk)
            f.write(chunk)
    if digest.hexdigest() != CYBERCHEF_SHA256:
        raise CyberChefInstallError('download does not match the pinned SHA-256')


def _extract_cyberchef(zip_path, dest):
    """Extract into dest, refusing absolute paths, '..' and symlinks."""
    dest_root = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            name = info.filename
            target = os.path.realpath(os.path.join(dest_root, name))
            is_symlink = (info.external_attr >> 16) & 0o170000 == 0o120000
            if (os.path.isabs(name) or name.startswith(('/', '\\')) or is_symlink
                    or not (target == dest_root or target.startswith(dest_root + os.sep))):
                raise CyberChefInstallError(f'unsafe path in archive: {name!r}')
        archive.extractall(dest_root)
    if not any(f.startswith('CyberChef') and f.endswith('.html') for f in os.listdir(dest_root)):
        raise CyberChefInstallError('archive does not contain CyberChef')


def _install_pinned_cyberchef():
    """Download, verify and unpack the pinned release, then swap it into place."""
    os.makedirs(TOOLS_DIR, exist_ok=True)
    work = tempfile.mkdtemp(prefix='cyberchef-', dir=TOOLS_DIR)
    try:
        zip_path = os.path.join(work, 'cyberchef.zip')
        staged = os.path.join(work, 'cyberchef')
        os.makedirs(staged)
        _download_pinned_cyberchef(zip_path)
        _extract_cyberchef(zip_path, staged)
        # Nothing on disk changed until here; swap the verified copy in.
        old = os.path.join(work, 'previous')
        if os.path.exists(CYBERCHEF_DIR):
            os.rename(CYBERCHEF_DIR, old)
        os.rename(staged, CYBERCHEF_DIR)
        save_cyberchef_version(CYBERCHEF_VERSION)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@admin_bp.route('/cyberchef/install', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def install_cyberchef():
    """Install the pinned CyberChef release (admin only)."""
    if not _cyberchef_install_lock.acquire(blocking=False):
        return jsonify({'error': 'A CyberChef install is already running'}), 409
    try:
        _install_pinned_cyberchef()
    except (requests.RequestException, CyberChefInstallError, zipfile.BadZipFile) as e:
        logger.warning('CyberChef install failed: %s', e)
        return jsonify({'error': f'CyberChef install failed: {e}'}), 502
    finally:
        _cyberchef_install_lock.release()
    AuditLogger.log_action(action='cyberchef_install', resource_type='tool',
                           details={'version': CYBERCHEF_VERSION, 'sha256': CYBERCHEF_SHA256})
    return jsonify({'success': True, 'version': CYBERCHEF_VERSION}), 200


@admin_bp.route('/cyberchef/update', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def update_cyberchef():
    """Reinstall CyberChef at the pinned version (admin only)."""
    old_version = get_cyberchef_version()
    result, status_code = install_cyberchef()
    if status_code == 200:
        return jsonify({
            'success': True,
            'old_version': old_version,
            'new_version': CYBERCHEF_VERSION,
        }), 200
    return result, status_code


def find_cyberchef_html():
    """Find the CyberChef HTML file (name includes version number)."""
    if not os.path.exists(CYBERCHEF_DIR):
        return None
    for f in os.listdir(CYBERCHEF_DIR):
        if f.startswith('CyberChef') and f.endswith('.html'):
            return f
    return None


@admin_bp.route('/cyberchef', methods=['GET'])
@require_auth
@handle_errors
def serve_cyberchef_redirect():
    """Redirect to trailing slash so relative URLs resolve correctly."""
    return redirect('/api/admin/cyberchef/', code=301)


def _send_cyberchef_file(filename):
    if not filename or not os.path.isdir(CYBERCHEF_DIR):
        return jsonify({'error': 'CyberChef not installed'}), 404
    root = os.path.realpath(CYBERCHEF_DIR)
    target = os.path.realpath(os.path.join(root, filename))
    if not target.startswith(root + os.sep) or not os.path.isfile(target):
        return jsonify({'error': 'File not found'}), 404
    response = send_from_directory(root, os.path.relpath(target, root))
    response.headers['Content-Security-Policy'] = CYBERCHEF_PAGE_CSP
    response.headers['Access-Control-Allow-Origin'] = '*'   # fonts requested from the opaque origin
    return response


@admin_bp.route('/cyberchef/', methods=['GET'])
@require_auth
@handle_errors
def serve_cyberchef():
    """Serve the CyberChef page (sandboxed, M-5)."""
    return _send_cyberchef_file(find_cyberchef_html())


@admin_bp.route('/cyberchef/<path:filename>', methods=['GET'])
@handle_errors
def serve_cyberchef_file(filename):
    """Serve CyberChef's own release files; the HTML page still needs a login."""
    if filename.lower().endswith(('.html', '.htm')):
        return serve_cyberchef_page_file(filename)
    return _send_cyberchef_file(filename)


@require_auth
def serve_cyberchef_page_file(filename):
    """A CyberChef HTML page by name; same login requirement as /cyberchef/."""
    return _send_cyberchef_file(filename)


@admin_bp.route('/settings', methods=['GET'])
@require_auth
@require_role('admin')
@handle_errors
def get_settings():
    """Get admin settings from the settings table."""
    cursor = g.db.cursor()
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('idle_timeout_minutes')")
    rows = cursor.fetchall()
    settings = {row[0]: row[1] for row in rows}

    return jsonify({
        'idle_timeout_minutes': int(settings.get('idle_timeout_minutes', 15)),
    }), 200


@admin_bp.route('/settings', methods=['PUT'])
@require_auth
@require_role('admin')
@handle_errors
def update_settings():
    """Update admin settings in the settings table."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    cursor = g.db.cursor()

    if 'idle_timeout_minutes' in data:
        try:
            val = int(data['idle_timeout_minutes'])
        except (ValueError, TypeError):
            return jsonify({'error': 'idle_timeout_minutes must be an integer'}), 400
        if val < 1 or val > 1440:
            return jsonify({'error': 'idle_timeout_minutes must be between 1 and 1440'}), 400
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES ('idle_timeout_minutes', ?, CURRENT_TIMESTAMP)
        ''', (str(val),))

    g.db.commit()

    # Clear the cached timeout so middleware picks up the new value
    _idle_timeout_cache.clear()

    return jsonify({
        'success': True,
        'idle_timeout_minutes': int(data.get('idle_timeout_minutes', 15)),
    }), 200


@admin_bp.route('/settings/idle-timeout', methods=['GET'])
@require_auth
@handle_errors
def get_idle_timeout():
    """Get idle timeout setting. Available to all authenticated users."""
    cursor = g.db.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'idle_timeout_minutes'")
    row = cursor.fetchone()
    timeout = int(row[0]) if row else 15
    return jsonify({'idle_timeout_minutes': timeout}), 200


# ============================================
# ENCRYPTION MANAGEMENT
# ============================================

@admin_bp.route('/encryption/available', methods=['GET'])
@handle_errors
def encryption_available():
    """Public endpoint: check if SQLCipher is available (no auth required).
    Used by the setup page to show/hide the encryption checkbox."""
    from models.encryption import is_encryption_available
    return jsonify({'available': is_encryption_available()}), 200


@admin_bp.route('/encryption/status', methods=['GET'])
@require_auth
@require_role('admin')
@handle_errors
def encryption_status():
    """Get database encryption status. Admin only."""
    from models.encryption import is_encryption_available, is_encryption_enabled, is_locked
    from config import Config

    return jsonify({
        'available': is_encryption_available(),
        'enabled': is_encryption_enabled(),
        'locked': is_locked(),
        # 'memory': the key is never written to disk (M-8); 'file': PTVAULT_STORE_KEY_FILE opt-in
        'key_storage': 'file' if Config.STORE_KEY_FILE else 'memory',
        'key_file_exists': os.path.exists(Config.ENCRYPTION_KEY_FILE),
        'salt_file_exists': os.path.exists(Config.ENCRYPTION_SALT_FILE),
        'encryption_required': Config.ENCRYPTION_REQUIRED
    }), 200


# There is no key recovery route (L-16): the key is derived from the passphrase
# and salt at /unlock (utils/unlock.py) after every restart. A recover route
# could only run while unlocked, where it re-ran unlock and saved nothing.


@admin_bp.route('/encryption/enable', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def encryption_enable():
    """
    Enable database encryption. Requires the passphrase the key is derived from.
    The key is held in memory, or also written to PTVAULT_ENCRYPTION_KEY_FILE
    with the PTVAULT_STORE_KEY_FILE opt-in. Admin only.
    """
    from models.encryption import is_encryption_available, is_encryption_enabled, setup_encryption
    from config import Config

    if not is_encryption_available():
        return jsonify({'error': 'pysqlcipher3 is not installed — cannot enable encryption'}), 400

    if is_encryption_enabled():
        return jsonify({'error': 'Encryption is already enabled'}), 400

    data = request.get_json()
    if not data or 'password' not in data:
        return jsonify({'error': 'Password is required to derive encryption key'}), 400
    # The passphrase is the only protection for the key (M-8): the same policy as
    # setup applies (M-12). ValidationError becomes a 400.
    if not isinstance(data['password'], str):
        return jsonify({'error': 'Password must be text'}), 400
    validate_password_strength(data['password'])

    # The key is held in memory (M-8). A key file location is set only through
    # PTVAULT_ENCRYPTION_KEY_FILE: accepting a path here let an admin write, and
    # on disable delete, a file anywhere the app can.
    if data.get('key_file_path'):
        return jsonify({'error': 'key_file_path is no longer accepted; the key is held in memory'}), 400

    try:
        # Close the active DB connection before migrating — the migration
        # needs exclusive access to checkpoint WAL and replace the file.
        db = g.pop('db', None)
        if db is not None:
            db.close()

        setup_encryption(data['password'])

        # Reopen connection (now encrypted) for audit logging
        from models.database import get_db_connection
        g.db = get_db_connection()

        # Evidence files are encrypted with the database key too (M-14)
        from models import upload_store
        upload_store.encrypt_existing()

        # Say where the key really is (L-16): a key file is named only when one
        # was written, so nobody backs up a file that does not exist.
        key_storage = 'file' if Config.STORE_KEY_FILE else 'memory'
        result = {'key_storage': key_storage, 'salt_file': Config.ENCRYPTION_SALT_FILE}
        if key_storage == 'file':
            result['key_file'] = Config.ENCRYPTION_KEY_FILE
        AuditLogger.log_action(action='encryption_enable', resource_type='database', details=result)
        message = ('Encryption enabled — the key is held in memory: after a restart, unlock with this passphrase'
                   if key_storage == 'memory' else 'Encryption enabled — the key is also stored in the key file')
        return jsonify({'success': True, 'message': message, **result}), 200
    except Exception as e:
        return internal_error(e, 'Failed to enable encryption')


@admin_bp.route('/revoke-sessions', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def revoke_all_user_sessions():
    """Revoke all active sessions (admin only). Forces re-login for everyone."""
    cursor = g.db.cursor()
    cursor.execute('UPDATE user_sessions SET is_active = 0')
    g.db.commit()
    count = cursor.rowcount
    return jsonify({"status": "ok", "revoked": count}), 200


@admin_bp.route('/encryption/disable', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def encryption_disable():
    """
    Disable database encryption. Decrypts the database and removes the key file.
    Admin only.
    """
    from models.encryption import is_encryption_enabled, disable_encryption
    from config import Config

    if not is_encryption_enabled():
        return jsonify({'error': 'Encryption is not currently enabled'}), 400

    if Config.ENCRYPTION_REQUIRED:
        return jsonify({'error': 'Cannot disable encryption: encryption is required (PTVAULT_ENCRYPTION_REQUIRED, on by default; set it to 0 to allow this)'}), 400

    try:
        # Close the active DB connection before migrating — the migration
        # needs exclusive access to checkpoint WAL and replace the file.
        db = g.pop('db', None)
        if db is not None:
            db.close()

        # Decrypt evidence files while the key is still known (M-14); if one does
        # not open, stop before the database is decrypted and the key forgotten.
        from models import upload_store
        try:
            upload_store.decrypt_existing()
        except upload_store.UploadDecryptError as e:
            logging.getLogger(__name__).error('Encryption not disabled: %s', e)
            return jsonify({'error': 'An evidence file could not be decrypted, so encryption was not '
                                     'disabled. See the server log.'}), 500

        disable_encryption()

        # Reopen connection (now plaintext) for audit logging
        from models.database import get_db_connection
        g.db = get_db_connection()

        AuditLogger.log_action(
            action='encryption_disable',
            resource_type='database'
        )
        return jsonify({
            'success': True,
            'message': 'Encryption disabled — database has been decrypted'
        }), 200
    except Exception as e:
        return internal_error(e, 'Failed to disable encryption')

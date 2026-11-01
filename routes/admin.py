"""Admin panel routes for PTVault."""

from flask import Blueprint, request, jsonify, g, send_from_directory, redirect
from middleware.auth import require_auth, require_role
from models.auth import revoke_all_sessions
from utils.audit_logger import AuditLogger
from utils.error_handler import handle_errors
import os
import json
import zipfile
import requests
import shutil
from datetime import datetime, timezone

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

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
CYBERCHEF_GITHUB_API = 'https://api.github.com/repos/gchq/CyberChef/releases/latest'


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
@handle_errors
def check_cyberchef_update():
    """Check GitHub for CyberChef updates."""
    try:
        response = requests.get(CYBERCHEF_GITHUB_API, timeout=10)
        response.raise_for_status()
        release_data = response.json()

        latest_version = release_data.get('tag_name', '')
        current_version = get_cyberchef_version()

        # Find the zip asset
        download_url = None
        for asset in release_data.get('assets', []):
            if asset['name'].endswith('.zip') and 'CyberChef' in asset['name']:
                download_url = asset['browser_download_url']
                break

        update_available = current_version != latest_version if current_version else True

        return jsonify({
            'current_version': current_version,
            'latest_version': latest_version,
            'update_available': update_available,
            'download_url': download_url
        }), 200

    except requests.RequestException as e:
        return jsonify({'error': f'Failed to check for updates: {str(e)}'}), 500


@admin_bp.route('/cyberchef/install', methods=['POST'])
@require_auth
@handle_errors
def install_cyberchef():
    """Download and install CyberChef."""
    try:
        # Get latest release info
        response = requests.get(CYBERCHEF_GITHUB_API, timeout=10)
        response.raise_for_status()
        release_data = response.json()

        version = release_data.get('tag_name', 'unknown')

        # Find download URL
        download_url = None
        for asset in release_data.get('assets', []):
            if asset['name'].endswith('.zip') and 'CyberChef' in asset['name']:
                download_url = asset['browser_download_url']
                break

        if not download_url:
            return jsonify({'error': 'Could not find CyberChef download URL'}), 500

        # Create directories
        os.makedirs(TOOLS_DIR, exist_ok=True)

        # Download zip file
        zip_path = os.path.join(TOOLS_DIR, 'cyberchef_temp.zip')

        download_response = requests.get(download_url, stream=True, timeout=300)
        download_response.raise_for_status()

        with open(zip_path, 'wb') as f:
            for chunk in download_response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Remove existing installation
        if os.path.exists(CYBERCHEF_DIR):
            shutil.rmtree(CYBERCHEF_DIR)

        # Extract zip
        os.makedirs(CYBERCHEF_DIR, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(CYBERCHEF_DIR)

        # Clean up zip file
        os.remove(zip_path)

        # Save version info
        save_cyberchef_version(version)

        return jsonify({
            'success': True,
            'version': version
        }), 200

    except requests.RequestException as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500


@admin_bp.route('/cyberchef/update', methods=['POST'])
@require_auth
@handle_errors
def update_cyberchef():
    """Update CyberChef to latest version."""
    old_version = get_cyberchef_version()

    # Reuse install logic
    result, status_code = install_cyberchef()

    if status_code == 200:
        response_data = result.get_json()
        return jsonify({
            'success': True,
            'old_version': old_version,
            'new_version': response_data.get('version')
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


@admin_bp.route('/cyberchef/', methods=['GET'])
@admin_bp.route('/cyberchef/<path:filename>', methods=['GET'])
@require_auth
@handle_errors
def serve_cyberchef(filename=None):
    """Serve CyberChef files."""
    if not os.path.exists(CYBERCHEF_DIR):
        return jsonify({'error': 'CyberChef not installed'}), 404

    # If no filename specified, find the main HTML file
    if not filename:
        filename = find_cyberchef_html()
        if not filename:
            return jsonify({'error': 'CyberChef HTML not found'}), 404

    # Handle case where filename is empty
    if not filename:
        filename = 'CyberChef.html'

    file_path = os.path.join(CYBERCHEF_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    return send_from_directory(CYBERCHEF_DIR, filename)


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
    from models.encryption import is_encryption_available, is_encryption_enabled
    from config import Config

    return jsonify({
        'available': is_encryption_available(),
        'enabled': is_encryption_enabled(),
        'key_file_exists': os.path.exists(Config.ENCRYPTION_KEY_FILE),
        'salt_file_exists': os.path.exists(Config.ENCRYPTION_SALT_FILE),
        'encryption_required': Config.ENCRYPTION_REQUIRED
    }), 200


@admin_bp.route('/encryption/recover', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def encryption_recover():
    """
    Recover encryption key from password + salt file.
    Used when the key file is lost but the salt file still exists.
    Admin only.
    """
    from models.encryption import is_encryption_available, recover_key
    from config import Config

    if not is_encryption_available():
        return jsonify({'error': 'pysqlcipher3 is not installed'}), 400

    if not os.path.exists(Config.ENCRYPTION_SALT_FILE):
        return jsonify({'error': 'Salt file not found — cannot recover key'}), 400

    data = request.get_json()
    if not data or 'password' not in data:
        return jsonify({'error': 'Password is required'}), 400

    try:
        recover_key(data['password'])
        return jsonify({
            'success': True,
            'message': 'Encryption key recovered and saved'
        }), 200
    except Exception as e:
        return jsonify({'error': f'Key recovery failed: {str(e)}'}), 500


@admin_bp.route('/encryption/enable', methods=['POST'])
@require_auth
@require_role('admin')
@handle_errors
def encryption_enable():
    """
    Enable database encryption. Requires password to derive the key.
    Optionally accepts a custom key_file_path.
    Admin only.
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

    # Allow custom key file path
    key_path = data.get('key_file_path')
    if key_path:
        # Validate the path is within a writable directory
        key_dir = os.path.dirname(os.path.abspath(key_path))
        if not os.path.isdir(key_dir):
            return jsonify({'error': f'Directory does not exist: {key_dir}'}), 400
        Config.ENCRYPTION_KEY_FILE = os.path.abspath(key_path)

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

        AuditLogger.log_action(
            action='encryption_enable',
            resource_type='database',
            details={'key_file': Config.ENCRYPTION_KEY_FILE}
        )
        return jsonify({
            'success': True,
            'message': 'Encryption enabled — database has been encrypted',
            'key_file': Config.ENCRYPTION_KEY_FILE,
            'salt_file': Config.ENCRYPTION_SALT_FILE
        }), 200
    except Exception as e:
        return jsonify({'error': f'Failed to enable encryption: {str(e)}'}), 500


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
        return jsonify({'error': 'Cannot disable encryption — PTVAULT_ENCRYPTION_REQUIRED is set'}), 400

    try:
        # Close the active DB connection before migrating — the migration
        # needs exclusive access to checkpoint WAL and replace the file.
        db = g.pop('db', None)
        if db is not None:
            db.close()

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
        return jsonify({'error': f'Failed to disable encryption: {str(e)}'}), 500

"""Unlocking an encrypted database after a restart (M-8).

The key is held in memory only, so after a restart the database is locked.
Until it is unlocked, locked_gate() sends every page to /unlock and answers
API calls with 503 database_locked; POST /api/unlock takes the database
passphrase (the password chosen at setup).
"""

import logging

from flask import Blueprint, jsonify, redirect, render_template, request

from models import encryption

logger = logging.getLogger(__name__)

unlock_bp = Blueprint('unlock', __name__)

# Reachable while locked: the unlock page and its assets, health and the CSRF token
_OPEN_WHILE_LOCKED = frozenset(['/unlock', '/api/unlock', '/api/health', '/api/auth/csrf-token'])


def locked_gate():
    """before_request hook: nothing but unlocking works while the database is locked."""
    if request.path in _OPEN_WHILE_LOCKED or request.path.startswith('/static/'):
        return None
    if not encryption.is_locked():
        return None
    if request.path.startswith('/api/'):
        return jsonify({'error': 'database_locked'}), 503
    return redirect('/unlock')


@unlock_bp.route('/unlock', methods=['GET'])
def unlock_page():
    if not encryption.is_locked():
        return redirect('/')
    return render_template('unlock.html')


@unlock_bp.route('/api/unlock', methods=['POST'])
def unlock_database():
    if not encryption.is_locked():
        return jsonify({'status': 'unlocked'}), 200
    passphrase = (request.get_json(silent=True) or {}).get('passphrase')
    if not isinstance(passphrase, str) or not passphrase:
        return jsonify({'error': 'passphrase is required'}), 400
    try:
        encryption.unlock(passphrase)
    except encryption.InvalidPassphrase:
        logger.warning('Failed database unlock attempt from %s', request.remote_addr)
        return jsonify({'error': 'The passphrase does not open the database'}), 401

    # Migrations could not run while the database was locked
    try:
        from models.database import run_migrations
        run_migrations()
    except Exception:
        logger.exception('Migrations after unlock failed')
    logger.info('Database unlocked from %s', request.remote_addr)
    return jsonify({'status': 'unlocked'}), 200

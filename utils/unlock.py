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

    # Migrations could not run while the database was locked. If they fail, routes
    # that need the new schema would fail with 500 and no hint why, so stay locked
    # and say so; the details go to the log (L-17).
    try:
        from models import database
        # run_migrations() reports a failed migration by returning False
        if database.run_migrations() is False:
            raise RuntimeError('a migration failed (see the log above)')
    except Exception:
        logger.exception('Migrations after unlock failed; the database stays locked')
        encryption.lock()
        return jsonify({'error': 'migration_failed',
                        'message': 'The passphrase is correct, but the database could not be upgraded to this '
                                   'version of PTVault, so it stays locked. See the server log for details.'}), 500
    # Evidence stored before encryption covered uploads is encrypted now that the
    # key is available (M-14). A failure leaves those files readable as they
    # were, so it is logged rather than locking the database again.
    try:
        from models import upload_store
        upload_store.encrypt_existing()
    except Exception:
        logger.exception('Could not encrypt existing evidence files; they stay unencrypted for now')
    logger.info('Database unlocked from %s', request.remote_addr)
    return jsonify({'status': 'unlocked'}), 200

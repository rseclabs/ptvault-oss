"""Authentication routes for PTVault."""

import json
from flask import Blueprint, request, jsonify, make_response
import hashlib
from models.auth import (
    hash_master_password,
    verify_master_password,
    create_session_token,
    hash_password,
    verify_password,
    create_session_record,
    revoke_session
)
from middleware.auth import require_auth
from utils.csrf import issue_csrf_token, session_csrf_token, set_csrf_cookie
from config import Config
from models.database import get_db_connection
from models.encryption import is_encryption_available, setup_encryption
from utils.error_handler import (
    handle_errors,
    ValidationError,
    AuthenticationError,
    ConflictError,
    DatabaseError,
    require_fields,
    validate_password_strength,
    validate_max_length
)


auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/setup', methods=['POST'])
@handle_errors
def setup():
    """
    First-time setup: create admin user with email and password.
    Only allows one user to be created (the initial admin).
    For multi-user setups, use /api/users endpoint after initial setup.
    """
    data = request.get_json()
    require_fields(data, ['email', 'password'])

    email = data['email'].strip().lower()
    password = data['password']
    full_name = data.get('full_name', '').strip() or 'Administrator'

    # Derive username from email (part before @)
    username = email.split('@')[0]

    # Validate email format (basic check)
    if '@' not in email or '.' not in email.split('@')[-1]:
        raise ValidationError("Invalid email address", field='email')

    # Validate password strength
    validate_password_strength(password)
    validate_max_length(email, 255, 'email')
    validate_max_length(full_name, 255, 'full_name')

    try:
        conn = get_db_connection()
    except Exception as e:
        raise DatabaseError("Failed to connect to database", details={'original_error': str(e)})

    try:
        cursor = conn.cursor()

        # Check if any user already exists
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count > 0:
            raise ConflictError("Setup already completed. Please login instead.")

        # Hash password and create admin user
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, email, full_name, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, 'admin', 1)
        ''', (username, email, full_name, password_hash))
        conn.commit()
        user_id = cursor.lastrowid

        # Audit log initial admin setup
        try:
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 'setup', 'user', user_id,
                  json.dumps({'username': username, 'email': email}),
                  request.remote_addr,
                  request.headers.get('User-Agent')))
            conn.commit()
        except Exception:
            pass  # Don't fail setup if audit logging fails

        # Set up database encryption if pysqlcipher3 is available
        enable_encryption = data.get('enable_encryption', True)
        if enable_encryption and is_encryption_available():
            try:
                setup_encryption(password)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Encryption setup skipped: {e}")

        # Create JWT token and set session cookie (auto-login after setup)
        token = create_session_token(user_id, role='admin', username=username)

        # The account already exists; if the session row cannot be stored the
        # auto-login cookie is refused and the admin simply logs in again.
        try:
            create_session_record(conn, user_id, token)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Could not record setup session; log in manually")

        # Set httpOnly cookie
        response = make_response(jsonify({
            "status": "created",
            "user_id": user_id,
            "username": username,
            "email": email,
            "role": "admin"
        }))
        response.set_cookie(
            'auth_token',
            token,
            httponly=True,
            secure=(Config.ENVIRONMENT == 'production'),
            samesite='Lax',
            max_age=86400  # 24 hours
        )
        # CSRF token bound to this new session (L-8)
        set_csrf_cookie(response, session_csrf_token(token))

        return response, 201

    except (ConflictError, ValidationError):
        raise
    except Exception as e:
        raise DatabaseError("Failed to create user", details={'original_error': str(e)})
    finally:
        conn.close()


_DUMMY_HASH = []


def _dummy_password_hash():
    """An Argon2id hash of a random value, used to equalise login timing."""
    if not _DUMMY_HASH:
        import secrets
        _DUMMY_HASH.append(hash_password(secrets.token_hex(16)))
    return _DUMMY_HASH[0]


@auth_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    """
    Login with email and password.
    Returns JWT session token in httpOnly cookie.
    Also supports legacy master_password for backwards compatibility.
    """
    # Clear any stale session data (e.g., active_engagement_id from a previous session)
    from flask import session as flask_session
    flask_session.clear()

    data = request.get_json()

    # Support legacy master_password or new email/password
    if 'master_password' in data:
        # Legacy single-user mode
        password = data['master_password']
        email = None
        username = None
    elif 'email' in data:
        require_fields(data, ['email', 'password'])
        email = data['email'].strip().lower()
        password = data['password']
        username = None
    else:
        require_fields(data, ['username', 'password'])
        username = data['username']
        password = data['password']
        email = None

    try:
        conn = get_db_connection()
    except Exception as e:
        raise DatabaseError("Failed to connect to database", details={'original_error': str(e)})

    try:
        cursor = conn.cursor()

        # Find user by email, username, or first user (legacy)
        if email:
            cursor.execute('''
                SELECT id, username, password_hash, role, is_active
                FROM users WHERE LOWER(email) = ?
            ''', (email,))
        elif username:
            cursor.execute('''
                SELECT id, username, password_hash, role, is_active
                FROM users WHERE username = ?
            ''', (username,))
        else:
            # Legacy: get first user
            cursor.execute('''
                SELECT id, username, password_hash, role, is_active
                FROM users LIMIT 1
            ''')

        user = cursor.fetchone()

        # One generic error for every failure. Unknown accounts still pay for a
        # hash check, and the active flag is checked after the password, so
        # neither the response nor its timing reveals which accounts exist.
        if not user:
            verify_password(password, _dummy_password_hash())
            raise AuthenticationError("Invalid credentials")

        user_id, db_username, password_hash, role, is_active = user

        password_ok = verify_password(password, password_hash)
        if not password_ok or not is_active:
            raise AuthenticationError("Invalid credentials")

        # Update last login timestamp
        cursor.execute('''
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
        ''', (user_id,))
        conn.commit()

        # Audit log successful login
        try:
            cursor.execute('''
                INSERT INTO audit_log (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 'login', 'session', user_id,
                  json.dumps({'username': db_username}),
                  request.remote_addr,
                  request.headers.get('User-Agent')))
            conn.commit()
        except Exception:
            pass  # Don't fail login if audit logging fails

        # Create JWT token with role
        token = create_session_token(user_id, role=role, username=db_username)

        # A token is only accepted while its session row exists, so a failure
        # here must fail the login (it propagates to the DatabaseError below).
        create_session_record(conn, user_id, token)

        # Set httpOnly cookie
        response = make_response(jsonify({
            "status": "authenticated",
            "user_id": user_id,
            "username": db_username,
            "role": role
        }))
        response.set_cookie(
            'auth_token',
            token,
            httponly=True,
            secure=(Config.ENVIRONMENT == 'production'),
            samesite='Lax',
            max_age=86400  # 24 hours
        )
        # CSRF token bound to this new session (L-8)
        set_csrf_cookie(response, session_csrf_token(token))

        return response, 200

    except (AuthenticationError, DatabaseError):
        raise
    except Exception as e:
        raise DatabaseError("Login failed", details={'original_error': str(e)})
    finally:
        conn.close()


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout: clear session cookie and revoke session."""
    token = request.cookies.get('auth_token')
    if token:
        try:
            from models.database import get_db_connection
            conn = get_db_connection()
            revoke_session(conn, token)
            conn.close()
        except Exception:
            pass
    from flask import session as flask_session
    flask_session.clear()
    response = make_response(jsonify({"status": "logged out"}))
    response.delete_cookie('auth_token')
    response.delete_cookie('csrf_token')
    return response, 200


@auth_bp.route('/heartbeat', methods=['POST'])
@require_auth
@handle_errors
def heartbeat():
    """Lightweight endpoint to keep session alive. Updates last_active."""
    token = request.cookies.get('auth_token')
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        from flask import g
        cursor = g.db.cursor()
        cursor.execute(
            'UPDATE user_sessions SET last_active = CURRENT_TIMESTAMP WHERE token_hash = ? AND is_active = 1',
            (token_hash,)
        )
        g.db.commit()

    from routes.admin import get_idle_timeout_minutes
    timeout = get_idle_timeout_minutes(g.db)
    return jsonify({"ok": True, "idle_timeout_minutes": timeout}), 200


@auth_bp.route('/csrf-token', methods=['GET'])
def get_csrf_token():
    """
    Get a CSRF token for the current session.
    Uses double-submit cookie pattern:
    - Sets csrf_token cookie
    - Returns token in response body
    - Client must send token in X-CSRF-Token header on mutating requests
    """
    # Bound to the session when logged in, random before login (utils/csrf.py, L-8)
    token = issue_csrf_token()
    response = make_response(jsonify({"csrf_token": token}))
    set_csrf_cookie(response, token)
    return response, 200

"""Authentication middleware for protected routes."""

import logging
from functools import wraps
from flask import request, jsonify, g, session
from models.auth import SESSION_IDLE, SESSION_OK, check_session, verify_session_token
from models.database import get_db_connection

logger = logging.getLogger(__name__)

# NOTE: Inline migrations have been moved to models/migrations/versions/019_consolidate_middleware_tables.py


def require_auth(f):
    """
    Decorator to protect routes with JWT authentication.
    Extracts user from session cookie and stores in g.current_user.
    Also establishes database connection.
    Provides g.active_engagement_id from session for engagement context.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract auth token cookie
        token = request.cookies.get('auth_token')
        if not token:
            return jsonify({"error": "unauthorized"}), 401

        # Verify JWT token
        payload = verify_session_token(token)
        if not payload:
            return jsonify({"error": "unauthorized"}), 401

        # Store user info in g context
        g.current_user = payload.get('user_id')
        g.current_user_role = payload.get('role', 'tester')
        g.current_username = payload.get('username')

        # Establish database connection
        try:
            g.db = get_db_connection()
        except Exception as e:
            return jsonify({"error": f"database connection failed: {str(e)}"}), 500

        # Every JWT must match an active, unexpired, non-idle session row.
        # Fail closed: an error here refuses the request.
        try:
            from routes.admin import get_idle_timeout_minutes
            status = check_session(g.db, token, get_idle_timeout_minutes(g.db))
        except Exception:
            logger.exception("Session validation failed; refusing request")
            return jsonify({"error": "session validation failed"}), 500

        if status == SESSION_IDLE:
            session.clear()
            return jsonify({"error": "session_idle_timeout"}), 401
        if status != SESSION_OK:
            session.clear()
            return jsonify({"error": "session revoked"}), 401

        # Set active engagement ID from session
        g.active_engagement_id = session.get('active_engagement_id')

        return f(*args, **kwargs)

    return decorated_function


def require_role(*allowed_roles):
    """
    Decorator to require specific role(s).
    Must be used after @require_auth.

    Args:
        *allowed_roles: Role names that are allowed (e.g., 'admin', 'tester')

    Example:
        @require_auth
        @require_role('admin')
        def admin_only_route():
            pass

        @require_auth
        @require_role('admin', 'tester')
        def admin_or_tester_route():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user_role'):
                return jsonify({"error": "authentication required"}), 401

            if g.current_user_role not in allowed_roles:
                return jsonify({"error": "insufficient permissions"}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_engagement_access(required_role='viewer'):
    """
    Decorator to check engagement-specific access.
    Must be used after @require_auth.

    Role hierarchy:
    - owner: Full control (edit, delete, add members)
    - editor: Can modify evidence, hosts, reports
    - viewer: Read-only access

    Args:
        required_role: Minimum role required (owner, editor, viewer)

    Example:
        @require_auth
        @require_engagement_access('editor')
        def update_evidence(evidence_id):
            pass
    """
    role_hierarchy = {'owner': 3, 'editor': 2, 'viewer': 1}

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'active_engagement_id'):
                return jsonify({"error": "no active engagement"}), 400

            if not g.active_engagement_id:
                return jsonify({"error": "no active engagement"}), 400

            # Admins have access to all engagements
            if g.current_user_role == 'admin':
                g.engagement_role = 'owner'
                return f(*args, **kwargs)

            # Check direct engagement membership first
            cursor = g.db.cursor()
            cursor.execute('''
                SELECT role FROM engagement_members
                WHERE engagement_id = ? AND user_id = ?
            ''', (g.active_engagement_id, g.current_user))

            row = cursor.fetchone()
            user_role = None

            if row:
                # Direct membership takes priority
                user_role = row[0]
            else:
                # Fallback: check team membership
                cursor.execute('''
                    SELECT tm.role FROM team_members tm
                    JOIN engagements e ON e.team_id = tm.team_id
                    WHERE e.id = ? AND tm.user_id = ?
                ''', (g.active_engagement_id, g.current_user))
                team_row = cursor.fetchone()
                if team_row:
                    # Map team roles to engagement roles: lead→editor, member→viewer
                    team_role = team_row[0]
                    user_role = 'editor' if team_role == 'lead' else 'viewer'

            if not user_role:
                return jsonify({"error": "not a member of this engagement"}), 403

            # Check role hierarchy
            if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role, 0):
                return jsonify({"error": "insufficient permissions"}), 403

            g.engagement_role = user_role
            return f(*args, **kwargs)
        return decorated_function
    return decorator

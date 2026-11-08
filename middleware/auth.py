"""Authentication middleware for protected routes."""

import logging
from functools import wraps
from flask import request, jsonify, g, session
from models.auth import SESSION_IDLE, SESSION_OK, check_session, verify_session_token
from models.database import get_db_connection

logger = logging.getLogger(__name__)

ENGAGEMENT_ROLE_RANK = {'viewer': 1, 'editor': 2, 'owner': 3}


def engagement_role(db, user_id, global_role, engagement_id):
    """Return the user's role on an engagement: 'owner', 'editor', 'viewer' or None.

    None means no access, including when the engagement does not exist.
    Admins are owners of every engagement. Direct membership wins over team
    membership; a team lead is an editor and a team member a viewer. A global
    viewer is read-only everywhere, so its role is capped at 'viewer'.
    """
    engagement = db.execute('SELECT team_id FROM engagements WHERE id = ?', (engagement_id,)).fetchone()
    if engagement is None:
        return None
    if global_role == 'admin':
        return 'owner'

    role = None
    member = db.execute(
        'SELECT role FROM engagement_members WHERE engagement_id = ? AND user_id = ?',
        (engagement_id, user_id)
    ).fetchone()
    if member is not None:
        role = member[0] if member[0] in ENGAGEMENT_ROLE_RANK else 'viewer'
    elif engagement[0] is not None:
        team = db.execute(
            'SELECT role FROM team_members WHERE team_id = ? AND user_id = ?', (engagement[0], user_id)
        ).fetchone()
        if team is not None:
            role = 'editor' if team[0] == 'lead' else 'viewer'

    if role is not None and global_role == 'viewer':
        return 'viewer'
    return role


def require_engagement_role(min_role='viewer', param='engagement_id'):
    """Require a role on the engagement named in the URL. Use after @require_auth.

    The engagement comes from the route's `param` argument, never from the
    session or the request body. No access (or no such engagement) is 404 so
    engagement ids cannot be probed; a role below min_role is 403. Sets
    g.engagement_role.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            role = engagement_role(g.db, g.current_user, g.current_user_role, kwargs[param])
            if role is None:
                return jsonify({"error": "engagement not found"}), 404
            if ENGAGEMENT_ROLE_RANK[role] < ENGAGEMENT_ROLE_RANK[min_role]:
                return jsonify({"error": "insufficient permissions"}), 403
            g.engagement_role = role
            return f(*args, **kwargs)
        return decorated_function
    return decorator

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

        # The token identifies the user; role and account state are read from
        # the database below, so the token's own claims are not trusted.
        g.current_user = payload.get('user_id')

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
            user = g.db.execute(
                'SELECT role, is_active, username FROM users WHERE id = ?', (g.current_user,)
            ).fetchone()
        except Exception:
            logger.exception("Session validation failed; refusing request")
            return jsonify({"error": "session validation failed"}), 500

        if status == SESSION_IDLE:
            session.clear()
            return jsonify({"error": "session_idle_timeout"}), 401
        if status != SESSION_OK:
            session.clear()
            return jsonify({"error": "session revoked"}), 401
        if user is None or not user[1]:
            session.clear()
            return jsonify({"error": "account disabled"}), 401

        g.current_user_role = user[0]
        g.current_username = user[2]

        # The active engagement lives in the session cookie; honour it only
        # while the user still has access to that engagement.
        active_id = session.get('active_engagement_id')
        if active_id is not None:
            try:
                if engagement_role(g.db, g.current_user, g.current_user_role, active_id) is None:
                    session.pop('active_engagement_id', None)
                    active_id = None
            except Exception:
                logger.exception("Engagement access check failed; refusing request")
                return jsonify({"error": "session validation failed"}), 500
        g.active_engagement_id = active_id

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
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not getattr(g, 'active_engagement_id', None):
                return jsonify({"error": "no active engagement"}), 400

            user_role = engagement_role(g.db, g.current_user, g.current_user_role, g.active_engagement_id)
            if not user_role:
                return jsonify({"error": "not a member of this engagement"}), 403

            if ENGAGEMENT_ROLE_RANK[user_role] < ENGAGEMENT_ROLE_RANK.get(required_role, 0):
                return jsonify({"error": "insufficient permissions"}), 403

            g.engagement_role = user_role
            return f(*args, **kwargs)
        return decorated_function
    return decorator

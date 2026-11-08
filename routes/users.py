"""User management routes for PTVault multi-user support."""

from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth, require_role

from models.dao.user_dao import UserDAO
import hashlib

from models.auth import hash_password, verify_password
from utils.error_handler import (
    handle_errors,
    ValidationError,
    NotFoundError,
    ConflictError,
    ForbiddenError,
    validate_password_strength,
    validate_max_length
)
import logging

from utils.audit_logger import audit_create, audit_update

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__, url_prefix='/api/users')
user_dao = UserDAO()


def _normalise_email(email):
    """Emails are stored and compared in lower case without surrounding spaces."""
    return (email or '').strip().lower()


def _active_admin_count():
    return user_dao.count({'role': 'admin', 'is_active': 1})


@users_bp.route('', methods=['GET'])
@require_auth
@require_role('admin')

@handle_errors
def list_users():
    """
    List all users (admin only).
    Returns users without password hashes.
    """
    users = user_dao.get_active_users()
    return jsonify({"users": users}), 200


@users_bp.route('/<int:user_id>', methods=['GET'])
@require_auth

@handle_errors
def get_user(user_id):
    """
    Get user by ID.
    Users can view their own profile, admins can view any user.
    """
    # Check permissions
    if g.current_user != user_id and g.current_user_role != 'admin':
        raise ForbiddenError("You can only view your own profile")

    user = user_dao.find_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")

    # Remove password hash for security
    user.pop('password_hash', None)

    return jsonify(user), 200


@users_bp.route('', methods=['POST'])
@require_auth
@require_role('admin')

@handle_errors
def create_user():
    """
    Create new user (admin only).

    Request body:
    {
        "username": "string (required)",
        "email": "string (required)",
        "password": "string (required)",
        "role": "admin|tester|viewer (default: tester)",
        "full_name": "string (optional)"
    }
    """
    data = request.get_json()

    # Validate required fields
    if not all(k in data for k in ['username', 'email', 'password']):
        raise ValidationError("username, email, and password are required")

    username = data['username']
    email = _normalise_email(data['email'])
    password = data['password']
    role = data.get('role', 'tester')
    full_name = data.get('full_name')

    # Validate password strength
    validate_password_strength(password)
    validate_max_length(username, 100, 'username')
    validate_max_length(email, 255, 'email')

    # Validate role
    if role not in ['admin', 'tester', 'viewer']:
        raise ValidationError("Invalid role. Must be: admin, tester, or viewer")

    # Check if username already exists
    if user_dao.find_by_username(username):
        raise ConflictError(f"Username '{username}' already exists")

    # Check if email already exists
    if user_dao.find_by_email(email):
        raise ConflictError(f"Email '{email}' already exists")

    # Hash password
    password_hash = hash_password(password)

    # Create user
    try:
        user_id = user_dao.create_user(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            full_name=full_name,
            created_by=g.current_user
        )

        logger.info(f"User created: {username} (id={user_id}) by user {g.current_user}")
        audit_create('user', user_id, username=username, role=role)

        return jsonify({
            "id": user_id,
            "username": username,
            "email": email,
            "role": role
        }), 201

    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise ValidationError("Failed to create user")


@users_bp.route('/<int:user_id>', methods=['PUT'])
@require_auth

@handle_errors
def update_user(user_id):
    """
    Update user information.
    Users can update their own profile (except role).
    Admins can update any user.

    Request body:
    {
        "full_name": "string (optional)",
        "email": "string (optional)",
        "password": "string (optional)",
        "role": "admin|tester|viewer (admin only)"
    }
    """
    # Check permissions
    if g.current_user != user_id and g.current_user_role != 'admin':
        raise ForbiddenError("You can only update your own profile")

    # Check user exists
    user = user_dao.find_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")

    data = request.get_json()
    update_data = {}

    # Handle fields
    if 'full_name' in data:
        update_data['full_name'] = data['full_name']

    if 'email' in data:
        email = _normalise_email(data['email'])
        existing = user_dao.find_by_email(email)
        if existing and existing['id'] != user_id:
            raise ConflictError(f"Email '{email}' already exists")
        update_data['email'] = email

    password_changed = False
    if 'password' in data:
        validate_password_strength(data['password'])
        if user_id == g.current_user:
            # Changing your own password needs the current one, so a stolen
            # session alone cannot take over the account.
            current = data.get('current_password')
            if not current:
                raise ValidationError("current_password is required to change your own password")
            if not verify_password(current, user['password_hash']):
                raise ForbiddenError("Current password is incorrect")
        update_data['password_hash'] = hash_password(data['password'])
        password_changed = True

    # Only admins can change roles
    if 'role' in data:
        if g.current_user_role != 'admin':
            raise ForbiddenError("Only admins can change user roles")

        if data['role'] not in ['admin', 'tester', 'viewer']:
            raise ValidationError("Invalid role")

        if user.get('role') == 'admin' and data['role'] != 'admin' and user.get('is_active') \
                and _active_admin_count() <= 1:
            raise ValidationError("Cannot demote the last admin user")

        update_data['role'] = data['role']

    # Perform update
    if not update_data:
        raise ValidationError("No fields to update")

    success = user_dao.update(user_id, update_data)
    if not success:
        raise NotFoundError("User not found")

    if password_changed:
        # Sign the user out everywhere else; keep the session making this
        # request when users change their own password.
        keep = ''
        if user_id == g.current_user and request.cookies.get('auth_token'):
            keep = hashlib.sha256(request.cookies['auth_token'].encode()).hexdigest()
        g.db.execute('UPDATE user_sessions SET is_active = 0 WHERE user_id = ? AND token_hash != ?',
                     (user_id, keep))
        g.db.commit()

    logger.info(f"User updated: {user_id} by user {g.current_user}")
    audit_update('user', user_id, updated_by=g.current_user, password_changed=password_changed)

    return jsonify({"status": "updated"}), 200


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@require_auth
@require_role('admin')

@handle_errors
def delete_user_route(user_id):
    """
    Permanently delete a user (admin only).
    Users cannot delete themselves. The last remaining admin cannot be
    deleted to avoid locking everyone out of the application.
    """
    if user_id == g.current_user:
        raise ValidationError("You cannot delete yourself")

    user = user_dao.find_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")

    if user.get('role') == 'admin':
        admin_count = user_dao.count({'role': 'admin', 'is_active': 1})
        if admin_count <= 1:
            raise ValidationError("Cannot delete the last admin user")

    audit_update('user', user_id, action='delete', deleted_by=g.current_user,
                 username=user.get('username'))

    success = user_dao.delete_user(user_id)
    if not success:
        raise NotFoundError("User not found")

    logger.info(f"User deleted: {user_id} by admin {g.current_user}")

    return jsonify({"status": "deleted"}), 200


@users_bp.route('/<int:user_id>/activate', methods=['POST'])
@require_auth
@require_role('admin')

@handle_errors
def activate_user_route(user_id):
    """
    Activate user (admin only).
    """
    user = user_dao.find_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")

    success = user_dao.activate_user(user_id)
    if not success:
        raise NotFoundError("User not found")

    logger.info(f"User activated: {user_id} by admin {g.current_user}")
    audit_update('user', user_id, action='activate', activated_by=g.current_user)

    return jsonify({"status": "activated"}), 200


@users_bp.route('/me', methods=['GET'])
@require_auth

@handle_errors
def get_current_user():
    """
    Get current user's profile.
    """
    user = user_dao.find_by_id(g.current_user)
    if not user:
        raise NotFoundError("User not found")

    # Remove password hash
    user.pop('password_hash', None)

    # Add engagement access info
    user['engagements'] = user_dao.get_user_engagements(g.current_user)

    return jsonify(user), 200


@users_bp.route('/me/engagements', methods=['GET'])
@require_auth

@handle_errors
def get_current_user_engagements():
    """
    Get engagements the current user has access to.
    """
    engagements = user_dao.get_user_engagements(g.current_user)
    return jsonify({"engagements": engagements}), 200

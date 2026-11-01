"""Engagement members management routes for team collaboration."""

from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth, require_engagement_access
from models.dao.user_dao import UserDAO
from utils.error_handler import (
    handle_errors,
    ValidationError,
    NotFoundError,
    ConflictError,
    ForbiddenError
)
import logging

logger = logging.getLogger(__name__)

engagement_members_bp = Blueprint('engagement_members', __name__,
                                 url_prefix='/api/engagements/<int:engagement_id>/members')
user_dao = UserDAO()


@engagement_members_bp.route('', methods=['GET'])
@require_auth
@require_engagement_access('viewer')
@handle_errors
def list_members(engagement_id):
    """
    List all members of an engagement.
    Accessible to any member with viewer access or higher.
    """
    cursor = g.db.cursor()
    cursor.execute('''
        SELECT
            em.id,
            em.user_id,
            u.username,
            u.email,
            u.full_name,
            u.role as system_role,
            em.role as engagement_role,
            em.added_at,
            adder.username as added_by_username
        FROM engagement_members em
        JOIN users u ON em.user_id = u.id
        LEFT JOIN users adder ON em.added_by = adder.id
        WHERE em.engagement_id = ?
        ORDER BY em.added_at ASC
    ''', (engagement_id,))

    members = [dict(row) for row in cursor.fetchall()]

    return jsonify({"members": members}), 200


@engagement_members_bp.route('', methods=['POST'])
@require_auth
@require_engagement_access('owner')
@handle_errors
def add_member(engagement_id):
    """
    Add a member to an engagement (owner only).

    Request body:
    {
        "user_id": integer (required),
        "role": "owner|editor|viewer" (default: editor)
    }
    """
    data = request.get_json()

    if 'user_id' not in data:
        raise ValidationError("user_id is required")

    user_id = data['user_id']
    role = data.get('role', 'editor')

    # Validate role
    if role not in ['owner', 'editor', 'viewer']:
        raise ValidationError("Invalid role. Must be: owner, editor, or viewer")

    # Check if user exists
    user = user_dao.find_by_id(user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")

    # Check if user is active
    if not user.get('is_active'):
        raise ValidationError("Cannot add deactivated user")

    # Check if already a member
    cursor = g.db.cursor()
    cursor.execute('''
        SELECT id FROM engagement_members
        WHERE engagement_id = ? AND user_id = ?
    ''', (engagement_id, user_id))

    if cursor.fetchone():
        raise ConflictError("User is already a member of this engagement")

    # Add member
    cursor.execute('''
        INSERT INTO engagement_members (engagement_id, user_id, role, added_by)
        VALUES (?, ?, ?, ?)
    ''', (engagement_id, user_id, role, g.current_user))
    g.db.commit()

    member_id = cursor.lastrowid

    logger.info(f"User {user_id} added to engagement {engagement_id} as {role} by {g.current_user}")

    return jsonify({
        "id": member_id,
        "engagement_id": engagement_id,
        "user_id": user_id,
        "role": role,
        "username": user['username']
    }), 201


@engagement_members_bp.route('/<int:member_id>', methods=['PUT'])
@require_auth
@require_engagement_access('owner')
@handle_errors
def update_member(engagement_id, member_id):
    """
    Update member role (owner only).

    Request body:
    {
        "role": "owner|editor|viewer"
    }
    """
    data = request.get_json()

    if 'role' not in data:
        raise ValidationError("role is required")

    role = data['role']

    # Validate role
    if role not in ['owner', 'editor', 'viewer']:
        raise ValidationError("Invalid role. Must be: owner, editor, or viewer")

    # Check member exists
    cursor = g.db.cursor()
    cursor.execute('''
        SELECT user_id FROM engagement_members
        WHERE id = ? AND engagement_id = ?
    ''', (member_id, engagement_id))

    row = cursor.fetchone()
    if not row:
        raise NotFoundError("Member not found")

    user_id = row[0]

    # Prevent owner from downgrading themselves if they're the last owner
    if user_id == g.current_user and role != 'owner':
        cursor.execute('''
            SELECT COUNT(*) FROM engagement_members
            WHERE engagement_id = ? AND role = 'owner'
        ''', (engagement_id,))
        owner_count = cursor.fetchone()[0]

        if owner_count <= 1:
            raise ValidationError("Cannot downgrade yourself - engagement must have at least one owner")

    # Update role
    cursor.execute('''
        UPDATE engagement_members
        SET role = ?
        WHERE id = ? AND engagement_id = ?
    ''', (role, member_id, engagement_id))
    g.db.commit()

    if cursor.rowcount == 0:
        raise NotFoundError("Member not found")

    logger.info(f"Member {member_id} role updated to {role} in engagement {engagement_id} by {g.current_user}")

    return jsonify({"status": "updated", "role": role}), 200


@engagement_members_bp.route('/<int:member_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('owner')
@handle_errors
def remove_member(engagement_id, member_id):
    """
    Remove a member from an engagement (owner only).
    Cannot remove yourself if you're the last owner.
    """
    cursor = g.db.cursor()

    # Check member exists
    cursor.execute('''
        SELECT user_id, role FROM engagement_members
        WHERE id = ? AND engagement_id = ?
    ''', (member_id, engagement_id))

    row = cursor.fetchone()
    if not row:
        raise NotFoundError("Member not found")

    user_id, role = row

    # Prevent removing last owner
    if role == 'owner':
        cursor.execute('''
            SELECT COUNT(*) FROM engagement_members
            WHERE engagement_id = ? AND role = 'owner'
        ''', (engagement_id,))
        owner_count = cursor.fetchone()[0]

        if owner_count <= 1:
            raise ValidationError("Cannot remove the last owner of the engagement")

    # Remove member
    cursor.execute('''
        DELETE FROM engagement_members
        WHERE id = ? AND engagement_id = ?
    ''', (member_id, engagement_id))
    g.db.commit()

    if cursor.rowcount == 0:
        raise NotFoundError("Member not found")

    logger.info(f"User {user_id} removed from engagement {engagement_id} by {g.current_user}")

    return jsonify({"status": "removed"}), 200

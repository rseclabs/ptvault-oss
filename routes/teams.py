"""Team management routes for PTVault."""

import logging
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth, require_role

from models.dao.team_dao import TeamDAO
from utils.error_handler import handle_errors

logger = logging.getLogger(__name__)

teams_bp = Blueprint('teams', __name__, url_prefix='/api/teams')


def get_dao():
    return TeamDAO()


@teams_bp.route('', methods=['GET'])
@require_auth

@handle_errors
def list_teams():
    """List teams. Admins see all; others see only their teams."""
    dao = get_dao()
    if g.current_user_role == 'admin':
        teams = dao.find_all(order_by='name')
    else:
        teams = dao.find_all_for_user(g.current_user)
    return jsonify(teams), 200


@teams_bp.route('', methods=['POST'])
@require_auth
@require_role('admin')

@handle_errors
def create_team():
    """Create a new team. Admin only."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    name = data.get('name')
    if not name or not name.strip():
        return jsonify({"error": "name is required"}), 400

    description = data.get('description')

    dao = get_dao()

    # Check for duplicate name
    existing = dao.find_one({'name': name.strip()})
    if existing:
        return jsonify({"error": "a team with this name already exists"}), 409

    team_id = dao.create({
        'name': name.strip(),
        'description': description,
        'created_by': g.current_user
    })

    team = dao.find_by_id(team_id)
    return jsonify(team), 201


@teams_bp.route('/<int:team_id>', methods=['GET'])
@require_auth

@handle_errors
def get_team(team_id):
    """Get team detail. Admin or team member."""
    dao = get_dao()
    team = dao.find_by_id(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404

    if g.current_user_role != 'admin' and not dao.is_member(team_id, g.current_user):
        return jsonify({"error": "not a member of this team"}), 403

    return jsonify(team), 200


@teams_bp.route('/<int:team_id>', methods=['PUT'])
@require_auth
@require_role('admin')

@handle_errors
def update_team(team_id):
    """Update a team. Admin only."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    dao = get_dao()
    team = dao.find_by_id(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404

    update_data = {}
    if 'name' in data:
        name = data['name']
        if not name or not name.strip():
            return jsonify({"error": "name cannot be empty"}), 400
        # Check uniqueness excluding current team
        existing = dao.find_one({'name': name.strip()})
        if existing and existing['id'] != team_id:
            return jsonify({"error": "a team with this name already exists"}), 409
        update_data['name'] = name.strip()
    if 'description' in data:
        update_data['description'] = data['description']

    if not update_data:
        return jsonify({"error": "no fields to update"}), 400

    from datetime import datetime, timezone
    update_data['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    dao.update(team_id, update_data)

    team = dao.find_by_id(team_id)
    return jsonify(team), 200


@teams_bp.route('/<int:team_id>', methods=['DELETE'])
@require_auth
@require_role('admin')

@handle_errors
def delete_team(team_id):
    """Delete a team. Nullifies team_id on associated engagements. Admin only."""
    dao = get_dao()
    team = dao.find_by_id(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404

    cursor = g.db.cursor()
    # Nullify team_id on engagements
    cursor.execute('UPDATE engagements SET team_id = NULL WHERE team_id = ?', (team_id,))
    g.db.commit()

    dao.delete(team_id)
    return '', 204


# ============================================================================
# Team Members Endpoints
# ============================================================================

@teams_bp.route('/<int:team_id>/members', methods=['GET'])
@require_auth

@handle_errors
def list_members(team_id):
    """List team members. Admin or team member."""
    dao = get_dao()
    team = dao.find_by_id(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404

    if g.current_user_role != 'admin' and not dao.is_member(team_id, g.current_user):
        return jsonify({"error": "not a member of this team"}), 403

    members = dao.get_members(team_id)
    return jsonify({"members": members}), 200


@teams_bp.route('/<int:team_id>/members', methods=['POST'])
@require_auth
@require_role('admin')

@handle_errors
def add_member(team_id):
    """Add a member to a team. Admin only."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    user_id = data.get('user_id')
    role = data.get('role', 'member')

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    if role not in ('lead', 'member'):
        return jsonify({"error": "role must be 'lead' or 'member'"}), 400

    dao = get_dao()
    team = dao.find_by_id(team_id)
    if not team:
        return jsonify({"error": "team not found"}), 404

    # Check user exists
    cursor = g.db.cursor()
    cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
    if not cursor.fetchone():
        return jsonify({"error": "user not found"}), 404

    # Check not already a member
    if dao.is_member(team_id, user_id):
        return jsonify({"error": "user is already a member of this team"}), 409

    member_id = dao.add_member(team_id, user_id, role, g.current_user)
    member = dao.get_member_by_id(member_id)
    return jsonify(member), 201


@teams_bp.route('/<int:team_id>/members/<int:member_id>', methods=['PUT'])
@require_auth
@require_role('admin')

@handle_errors
def update_member(team_id, member_id):
    """Update a team member's role. Admin only."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    role = data.get('role')
    if not role or role not in ('lead', 'member'):
        return jsonify({"error": "role must be 'lead' or 'member'"}), 400

    dao = get_dao()
    member = dao.get_member_by_id(member_id)
    if not member or member['team_id'] != team_id:
        return jsonify({"error": "member not found"}), 404

    dao.update_member_role(member_id, role)
    member = dao.get_member_by_id(member_id)
    return jsonify(member), 200


@teams_bp.route('/<int:team_id>/members/<int:member_id>', methods=['DELETE'])
@require_auth
@require_role('admin')

@handle_errors
def remove_member(team_id, member_id):
    """Remove a member from a team. Admin only."""
    dao = get_dao()
    member = dao.get_member_by_id(member_id)
    if not member or member['team_id'] != team_id:
        return jsonify({"error": "member not found"}), 404

    dao.remove_member(member_id)
    return '', 204

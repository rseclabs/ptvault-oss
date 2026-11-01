"""Test routes for authentication verification."""

from flask import Blueprint, jsonify, g
from middleware.auth import require_auth


test_bp = Blueprint('test', __name__, url_prefix='/api')


@test_bp.route('/protected', methods=['GET'])
@require_auth
def protected():
    """Protected endpoint - requires authentication."""
    return jsonify({
        "message": "authenticated",
        "user_id": g.current_user
    }), 200


@test_bp.route('/public', methods=['GET'])
def public():
    """Public endpoint - no authentication required."""
    return jsonify({
        "message": "public endpoint"
    }), 200

"""Tag management routes for PTVault."""

from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from utils.error_handler import handle_errors

tags_bp = Blueprint('tags', __name__, url_prefix='/api/tags')


@tags_bp.route('/autocomplete', methods=['GET'])
@require_auth
@handle_errors
def autocomplete_tags():
    """
    Tag autocomplete endpoint with prefix search.
    Query param 'q' for prefix search, 'limit' for max results (default 10, max 50).
    Returns tags sorted by usage count (most used first).
    """
    prefix = request.args.get('q', '').strip().lower()
    limit = min(int(request.args.get('limit', 10)), 50)

    cursor = g.db.cursor()

    if not prefix:
        # Return most used tags if no prefix
        query = '''
            SELECT t.name, COUNT(et.evidence_id) as usage_count
            FROM tags t
            LEFT JOIN evidence_tags et ON t.id = et.tag_id
            GROUP BY t.id
            ORDER BY usage_count DESC
            LIMIT ?
        '''
        params = [limit]
    else:
        # Prefix search with usage count
        query = '''
            SELECT t.name, COUNT(et.evidence_id) as usage_count
            FROM tags t
            LEFT JOIN evidence_tags et ON t.id = et.tag_id
            WHERE t.name LIKE ?
            GROUP BY t.id
            ORDER BY usage_count DESC
            LIMIT ?
        '''
        params = [f'{prefix}%', limit]

    cursor.execute(query, params)
    rows = cursor.fetchall()

    return jsonify({
        'suggestions': [
            {'name': row[0], 'count': row[1]}
            for row in rows
        ]
    })

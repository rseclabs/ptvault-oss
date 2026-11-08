"""Tag management routes for PTVault."""

from collections import Counter

from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from utils.error_handler import handle_errors
from utils.helpers import bounded_int

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
    limit = bounded_int(request.args.get('limit'), 10, 1, 50)          # L-19

    # Suggest only tags used in the active engagement, counted from the
    # comma-separated evidence.tags column that every write path maintains.
    # (The global tags table is only filled by engagement import, and would
    # leak tag names from engagements the user cannot access.)
    engagement_id = getattr(g, 'active_engagement_id', None)
    if not engagement_id:
        return jsonify({'suggestions': []})

    cursor = g.db.cursor()
    cursor.execute(
        "SELECT tags FROM evidence WHERE engagement_id = ? AND tags IS NOT NULL AND tags != ''",
        (engagement_id,)
    )
    counts = Counter()
    for (tags,) in cursor.fetchall():
        counts.update({t.strip() for t in tags.split(',') if t.strip()})

    matches = [(name, n) for name, n in counts.items() if name.lower().startswith(prefix)]
    matches.sort(key=lambda item: (-item[1], item[0]))
    rows = matches[:limit]

    return jsonify({
        'suggestions': [
            {'name': row[0], 'count': row[1]}
            for row in rows
        ]
    })

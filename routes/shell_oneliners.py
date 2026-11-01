"""Shell one-liners routes for PTVault."""

from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from utils.error_handler import handle_errors
import json

shell_oneliners_bp = Blueprint('shell_oneliners', __name__, url_prefix='/api/shell-oneliners')


@shell_oneliners_bp.route('', methods=['GET'])
@require_auth
@handle_errors
def list_oneliners():
    """
    List all shell one-liners with optional filters.
    Query params:
        - category: Filter by category (shells, reverse_shells, shell_upgrades)
        - subcategory: Filter by subcategory (bash, python, etc.)
        - search: Search in name, command, description
    """
    cursor = g.db.cursor()

    # Build query with filters
    query = "SELECT * FROM shell_oneliners WHERE 1=1"
    params = []

    category = request.args.get('category')
    if category and category != 'all':
        query += " AND category = ?"
        params.append(category)

    subcategory = request.args.get('subcategory')
    if subcategory and subcategory != 'all':
        query += " AND subcategory = ?"
        params.append(subcategory)

    search = request.args.get('search')
    if search:
        query += " AND (name LIKE ? OR command LIKE ? OR description LIKE ?)"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    query += " ORDER BY category, subcategory, name ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Convert to list of dicts
    columns = [desc[0] for desc in cursor.description]
    oneliners = [dict(zip(columns, row)) for row in rows]

    # Parse variables JSON for each one-liner
    for item in oneliners:
        if item.get('variables'):
            try:
                item['variables'] = json.loads(item['variables'])
            except json.JSONDecodeError:
                item['variables'] = []

    return jsonify(oneliners), 200


@shell_oneliners_bp.route('/<int:oneliner_id>', methods=['GET'])
@require_auth
@handle_errors
def get_oneliner(oneliner_id):
    """Get a single shell one-liner by ID."""
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM shell_oneliners WHERE id = ?", (oneliner_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "One-liner not found"}), 404

    columns = [desc[0] for desc in cursor.description]
    oneliner = dict(zip(columns, row))

    # Parse variables JSON
    if oneliner.get('variables'):
        try:
            oneliner['variables'] = json.loads(oneliner['variables'])
        except json.JSONDecodeError:
            oneliner['variables'] = []

    return jsonify(oneliner), 200


@shell_oneliners_bp.route('/categories', methods=['GET'])
@require_auth
@handle_errors
def list_categories():
    """List all categories and subcategories with counts."""
    cursor = g.db.cursor()

    # Get categories with counts
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM shell_oneliners
        GROUP BY category
        ORDER BY
            CASE category
                WHEN 'shells' THEN 1
                WHEN 'reverse_shells' THEN 2
                WHEN 'shell_upgrades' THEN 3
                ELSE 4
            END
    ''')
    categories = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

    # Get subcategories with counts
    cursor.execute('''
        SELECT category, subcategory, COUNT(*) as count
        FROM shell_oneliners
        GROUP BY category, subcategory
        ORDER BY category, subcategory
    ''')
    subcategories = {}
    for row in cursor.fetchall():
        cat = row[0]
        if cat not in subcategories:
            subcategories[cat] = []
        subcategories[cat].append({"name": row[1], "count": row[2]})

    # Total count
    cursor.execute("SELECT COUNT(*) FROM shell_oneliners")
    total = cursor.fetchone()[0]

    return jsonify({
        "categories": categories,
        "subcategories": subcategories,
        "total": total
    }), 200


# ==================== Admin Endpoints ====================

@shell_oneliners_bp.route('/admin', methods=['POST'])
@require_auth
@handle_errors
def create_oneliner():
    """
    Create a new shell one-liner (admin only).
    Required: category, name, command
    Optional: subcategory, description, variables (JSON array)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    category = data.get('category')
    subcategory = data.get('subcategory')
    name = data.get('name')
    command = data.get('command')
    description = data.get('description', '')
    variables = data.get('variables', [])

    if not category:
        return jsonify({"error": "category is required"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not command:
        return jsonify({"error": "command is required"}), 400

    # Validate category
    valid_categories = ['shells', 'reverse_shells', 'shell_upgrades']
    if category not in valid_categories:
        return jsonify({"error": f"category must be one of: {', '.join(valid_categories)}"}), 400

    # Convert variables to JSON string
    variables_json = json.dumps(variables) if isinstance(variables, list) else variables

    cursor = g.db.cursor()
    cursor.execute('''
        INSERT INTO shell_oneliners (category, subcategory, name, command, description, variables, is_admin)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    ''', (category, subcategory, name, command, description, variables_json))

    g.db.commit()
    oneliner_id = cursor.lastrowid

    # Return the created one-liner
    cursor.execute("SELECT * FROM shell_oneliners WHERE id = ?", (oneliner_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    new_oneliner = dict(zip(columns, row))

    if new_oneliner.get('variables'):
        try:
            new_oneliner['variables'] = json.loads(new_oneliner['variables'])
        except json.JSONDecodeError:
            new_oneliner['variables'] = []

    return jsonify(new_oneliner), 201


@shell_oneliners_bp.route('/admin/<int:oneliner_id>', methods=['PUT'])
@require_auth
@handle_errors
def update_oneliner(oneliner_id):
    """
    Update a shell one-liner (admin only).
    """
    cursor = g.db.cursor()

    # Check if one-liner exists
    cursor.execute("SELECT id FROM shell_oneliners WHERE id = ?", (oneliner_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "One-liner not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Build update query dynamically
    updates = []
    params = []

    if 'category' in data:
        valid_categories = ['shells', 'reverse_shells', 'shell_upgrades']
        if data['category'] not in valid_categories:
            return jsonify({"error": f"category must be one of: {', '.join(valid_categories)}"}), 400
        updates.append("category = ?")
        params.append(data['category'])

    if 'subcategory' in data:
        updates.append("subcategory = ?")
        params.append(data['subcategory'])

    if 'name' in data:
        updates.append("name = ?")
        params.append(data['name'])

    if 'command' in data:
        updates.append("command = ?")
        params.append(data['command'])

    if 'description' in data:
        updates.append("description = ?")
        params.append(data['description'])

    if 'variables' in data:
        variables_json = json.dumps(data['variables']) if isinstance(data['variables'], list) else data['variables']
        updates.append("variables = ?")
        params.append(variables_json)

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    params.append(oneliner_id)
    query = f"UPDATE shell_oneliners SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    g.db.commit()

    # Return updated one-liner
    cursor.execute("SELECT * FROM shell_oneliners WHERE id = ?", (oneliner_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    updated_oneliner = dict(zip(columns, row))

    if updated_oneliner.get('variables'):
        try:
            updated_oneliner['variables'] = json.loads(updated_oneliner['variables'])
        except json.JSONDecodeError:
            updated_oneliner['variables'] = []

    return jsonify(updated_oneliner), 200


@shell_oneliners_bp.route('/admin/<int:oneliner_id>', methods=['DELETE'])
@require_auth
@handle_errors
def delete_oneliner(oneliner_id):
    """
    Delete a shell one-liner (admin only).
    """
    cursor = g.db.cursor()

    # Check if one-liner exists
    cursor.execute("SELECT id FROM shell_oneliners WHERE id = ?", (oneliner_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "One-liner not found"}), 404

    cursor.execute("DELETE FROM shell_oneliners WHERE id = ?", (oneliner_id,))
    g.db.commit()

    return jsonify({"success": True}), 200

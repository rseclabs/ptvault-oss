"""Command database routes for PTVault."""

from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from utils.error_handler import handle_errors
import json

commands_bp = Blueprint('commands', __name__, url_prefix='/api/commands')


@commands_bp.route('', methods=['GET'])
@require_auth
@handle_errors
def list_commands():
    """
    List all commands with optional filters.
    Query params:
        - category: Filter by category
        - search: Search in name, command, description
        - is_favorite: Filter favorites only (true/false)
    """
    cursor = g.db.cursor()

    # Build query with filters
    query = "SELECT * FROM commands WHERE 1=1"
    params = []

    category = request.args.get('category')
    if category and category != 'all':
        query += " AND category = ?"
        params.append(category)

    search = request.args.get('search')
    if search:
        query += " AND (name LIKE ? OR command LIKE ? OR description LIKE ?)"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    is_favorite = request.args.get('is_favorite')
    if is_favorite == 'true':
        query += " AND is_favorite = 1"

    query += " ORDER BY is_favorite DESC, usage_count DESC, name ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Convert to list of dicts
    columns = [desc[0] for desc in cursor.description]
    commands = [dict(zip(columns, row)) for row in rows]

    # Parse variables JSON for each command
    for cmd in commands:
        if cmd.get('variables'):
            try:
                cmd['variables'] = json.loads(cmd['variables'])
            except json.JSONDecodeError:
                cmd['variables'] = []

    return jsonify(commands), 200


@commands_bp.route('/<int:command_id>', methods=['GET'])
@require_auth
@handle_errors
def get_command(command_id):
    """Get a single command by ID."""
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM commands WHERE id = ?", (command_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Command not found"}), 404

    columns = [desc[0] for desc in cursor.description]
    command = dict(zip(columns, row))

    # Parse variables JSON
    if command.get('variables'):
        try:
            command['variables'] = json.loads(command['variables'])
        except json.JSONDecodeError:
            command['variables'] = []

    return jsonify(command), 200


@commands_bp.route('', methods=['POST'])
@require_auth
@handle_errors
def create_command():
    """
    Create a new custom command.
    Required: category, name, command
    Optional: description, variables (JSON array)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    category = data.get('category')
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
    valid_categories = ['Recon', 'Enumeration', 'Exploitation', 'Post-exploitation', 'Reporting']
    if category not in valid_categories:
        return jsonify({"error": f"category must be one of: {', '.join(valid_categories)}"}), 400

    # Convert variables to JSON string
    variables_json = json.dumps(variables) if isinstance(variables, list) else variables

    cursor = g.db.cursor()
    cursor.execute('''
        INSERT INTO commands (category, name, command, description, variables, is_custom)
        VALUES (?, ?, ?, ?, ?, 1)
    ''', (category, name, command, description, variables_json))

    g.db.commit()
    command_id = cursor.lastrowid

    # Return the created command
    cursor.execute("SELECT * FROM commands WHERE id = ?", (command_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    new_command = dict(zip(columns, row))

    if new_command.get('variables'):
        try:
            new_command['variables'] = json.loads(new_command['variables'])
        except json.JSONDecodeError:
            new_command['variables'] = []

    return jsonify(new_command), 201


@commands_bp.route('/<int:command_id>', methods=['PUT'])
@require_auth
@handle_errors
def update_command(command_id):
    """
    Update a command.
    Only allows updating custom commands (is_custom=1).
    """
    cursor = g.db.cursor()

    # Check if command exists and is custom
    cursor.execute("SELECT is_custom FROM commands WHERE id = ?", (command_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Command not found"}), 404

    if row[0] == 0:
        return jsonify({"error": "Cannot modify pre-built commands"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Build update query dynamically
    updates = []
    params = []

    if 'category' in data:
        valid_categories = ['Recon', 'Enumeration', 'Exploitation', 'Post-exploitation', 'Reporting']
        if data['category'] not in valid_categories:
            return jsonify({"error": f"category must be one of: {', '.join(valid_categories)}"}), 400
        updates.append("category = ?")
        params.append(data['category'])

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

    params.append(command_id)
    query = f"UPDATE commands SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    g.db.commit()

    # Return updated command
    cursor.execute("SELECT * FROM commands WHERE id = ?", (command_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    updated_command = dict(zip(columns, row))

    if updated_command.get('variables'):
        try:
            updated_command['variables'] = json.loads(updated_command['variables'])
        except json.JSONDecodeError:
            updated_command['variables'] = []

    return jsonify(updated_command), 200


@commands_bp.route('/<int:command_id>', methods=['DELETE'])
@require_auth
@handle_errors
def delete_command(command_id):
    """
    Delete a command.
    Only allows deleting custom commands (is_custom=1).
    """
    cursor = g.db.cursor()

    # Check if command exists and is custom
    cursor.execute("SELECT is_custom FROM commands WHERE id = ?", (command_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Command not found"}), 404

    if row[0] == 0:
        return jsonify({"error": "Cannot delete pre-built commands"}), 403

    cursor.execute("DELETE FROM commands WHERE id = ?", (command_id,))
    g.db.commit()

    return jsonify({"success": True}), 200


@commands_bp.route('/<int:command_id>/favorite', methods=['POST'])
@require_auth
@handle_errors
def toggle_favorite(command_id):
    """Toggle favorite status for a command."""
    cursor = g.db.cursor()

    # Check if command exists
    cursor.execute("SELECT is_favorite FROM commands WHERE id = ?", (command_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Command not found"}), 404

    new_status = 0 if row[0] == 1 else 1
    cursor.execute("UPDATE commands SET is_favorite = ? WHERE id = ?", (new_status, command_id))
    g.db.commit()

    return jsonify({"is_favorite": new_status}), 200


@commands_bp.route('/<int:command_id>/usage', methods=['POST'])
@require_auth
@handle_errors
def increment_usage(command_id):
    """Increment usage count (called when command is copied)."""
    cursor = g.db.cursor()

    cursor.execute("UPDATE commands SET usage_count = usage_count + 1 WHERE id = ?", (command_id,))
    g.db.commit()

    if cursor.rowcount == 0:
        return jsonify({"error": "Command not found"}), 404

    return jsonify({"success": True}), 200


@commands_bp.route('/categories', methods=['GET'])
@require_auth
@handle_errors
def list_categories():
    """List all available categories with command counts."""
    cursor = g.db.cursor()

    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM commands
        GROUP BY category
        ORDER BY
            CASE category
                WHEN 'Recon' THEN 1
                WHEN 'Enumeration' THEN 2
                WHEN 'Exploitation' THEN 3
                WHEN 'Post-exploitation' THEN 4
                WHEN 'Reporting' THEN 5
                ELSE 6
            END
    ''')

    rows = cursor.fetchall()
    categories = [{"name": row[0], "count": row[1]} for row in rows]

    # Add total count
    total = sum(cat['count'] for cat in categories)

    return jsonify({
        "categories": categories,
        "total": total
    }), 200

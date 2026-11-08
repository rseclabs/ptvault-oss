"""Attack Maps API endpoints.

REST API for managing attack maps, nodes, and edges.
Maps are visual diagrams showing how a network was compromised.
"""

import json
import logging
from flask import Blueprint, request, jsonify, g

from middleware.auth import require_auth, require_engagement_access
from models.dao.attack_map_dao import AttackMapDAO, AttackMapNodeDAO, AttackMapEdgeDAO
from utils.error_handler import handle_errors
from models.engagement_cleanup import delete_attack_map

logger = logging.getLogger(__name__)

attack_maps_bp = Blueprint('attack_maps', __name__, url_prefix='/api/attack-maps')


# ── Map CRUD ───────────────────────────────────────────────────────

@attack_maps_bp.route('', methods=['GET'])
@require_auth
@handle_errors
def list_maps():
    """List all maps for the active engagement."""
    dao = AttackMapDAO()
    maps = dao.find_all(order_by='updated_at DESC')
    return jsonify({"maps": maps}), 200


@attack_maps_bp.route('', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_map():
    """Create a new attack map."""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Map name is required"}), 400

    dao = AttackMapDAO()
    map_id = dao.create({
        'name': data['name'],
        'description': data.get('description', ''),
        'canvas_data': json.dumps(data.get('canvas_data', {})),
        'created_by': getattr(g, 'user_id', None)
    })

    attack_map = dao.find_by_id(map_id)
    return jsonify(attack_map), 201


@attack_maps_bp.route('/<int:map_id>', methods=['GET'])
@require_auth
@handle_errors
def get_map(map_id):
    """Get a map with all nodes and edges."""
    dao = AttackMapDAO()
    attack_map = dao.get_full_map(map_id)
    if not attack_map:
        return jsonify({"error": "Map not found"}), 404
    return jsonify(attack_map), 200


@attack_maps_bp.route('/<int:map_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def update_map(map_id):
    """Update map metadata or canvas_data."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    dao = AttackMapDAO()
    existing = dao.find_by_id(map_id)
    if not existing:
        return jsonify({"error": "Map not found"}), 404

    update_data = {}
    if 'name' in data:
        update_data['name'] = data['name']
    if 'description' in data:
        update_data['description'] = data['description']
    if 'canvas_data' in data:
        update_data['canvas_data'] = json.dumps(data['canvas_data']) if isinstance(data['canvas_data'], dict) else data['canvas_data']
    update_data['updated_at'] = 'CURRENT_TIMESTAMP'

    # Manual update to handle CURRENT_TIMESTAMP properly
    if update_data:
        cursor = g.db.cursor()
        set_parts = []
        values = []
        for key, val in update_data.items():
            if val == 'CURRENT_TIMESTAMP':
                set_parts.append(f"{key} = CURRENT_TIMESTAMP")
            else:
                set_parts.append(f"{key} = ?")
                values.append(val)
        values.append(map_id)
        eng_id = getattr(g, 'active_engagement_id', None)
        if eng_id:
            values.append(eng_id)
        query = f"UPDATE attack_maps SET {', '.join(set_parts)} WHERE id = ?"
        if eng_id:
            query += " AND engagement_id = ?"
        cursor.execute(query, values)
        g.db.commit()

    attack_map = dao.find_by_id(map_id)
    return jsonify(attack_map), 200


@attack_maps_bp.route('/<int:map_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_map(map_id):
    """Delete a map and all its nodes/edges (cascade)."""
    dao = AttackMapDAO()
    existing = dao.find_by_id(map_id)
    if not existing:
        return jsonify({"error": "Map not found"}), 404

    # Nodes and edges go too: foreign keys are not enforced, nothing cascades (L-24)
    delete_attack_map(g.db.cursor(), map_id)
    g.db.commit()
    return jsonify({"message": "Map deleted"}), 200


@attack_maps_bp.route('/<int:map_id>/duplicate', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def duplicate_map(map_id):
    """Duplicate a map with all nodes and edges."""
    dao = AttackMapDAO()
    new_map_id = dao.duplicate_map(map_id)
    if not new_map_id:
        return jsonify({"error": "Map not found"}), 404

    new_map = dao.get_full_map(new_map_id)
    return jsonify(new_map), 201


# ── Node CRUD ──────────────────────────────────────────────────────

def _properties_json(value):
    """(JSON text, None) for a node's properties, or (None, 400 response).

    Properties are an object; null clears them. Anything else used to be stored
    as given and broke the SVG export with a 500.
    """
    if value is None:
        return '{}', None
    if isinstance(value, dict):
        return json.dumps(value), None
    return None, (jsonify({"error": "properties must be an object"}), 400)


@attack_maps_bp.route('/<int:map_id>/nodes', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_node(map_id):
    """Create a node on a map."""
    # Verify map exists and belongs to engagement
    map_dao = AttackMapDAO()
    if not map_dao.find_by_id(map_id):
        return jsonify({"error": "Map not found"}), 404

    data = request.get_json()
    if not data or not data.get('node_type'):
        return jsonify({"error": "node_type is required"}), 400

    node_dao = AttackMapNodeDAO()
    properties, error = _properties_json(data.get('properties'))
    if error:
        return error

    node_id = node_dao.create({
        'map_id': map_id,
        'node_type': data['node_type'],
        'x': data.get('x', 100),
        'y': data.get('y', 100),
        'width': data.get('width', 220),
        'height': data.get('height', 80),
        'label': data.get('label', ''),
        'properties': properties,
        'ref_id': data.get('ref_id'),
        'ref_type': data.get('ref_type')
    })

    # Touch map updated_at
    _touch_map(map_id)

    node = node_dao.find_by_id(node_id)
    if node and node.get('properties') and isinstance(node['properties'], str):
        try:
            node['properties'] = json.loads(node['properties'])
        except (json.JSONDecodeError, TypeError):
            node['properties'] = {}
    return jsonify(node), 201


@attack_maps_bp.route('/<int:map_id>/nodes/<int:node_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def update_node(map_id, node_id):
    """Update a node's position or properties."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    if not _map_in_engagement(map_id):
        return jsonify({"error": "Map not found"}), 404

    node_dao = AttackMapNodeDAO()
    existing = node_dao.find_by_id(node_id)
    if not existing or existing['map_id'] != map_id:
        return jsonify({"error": "Node not found"}), 404

    update_data = {}
    for field in ('x', 'y', 'width', 'height', 'label', 'node_type', 'ref_id', 'ref_type'):
        if field in data:
            update_data[field] = data[field]
    if 'properties' in data:
        update_data['properties'], error = _properties_json(data['properties'])
        if error:
            return error

    if update_data:
        node_dao.update(node_id, update_data)
        _touch_map(map_id)

    node = node_dao.find_by_id(node_id)
    if node and node.get('properties') and isinstance(node['properties'], str):
        try:
            node['properties'] = json.loads(node['properties'])
        except (json.JSONDecodeError, TypeError):
            node['properties'] = {}
    return jsonify(node), 200


@attack_maps_bp.route('/<int:map_id>/nodes/<int:node_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_node(map_id, node_id):
    """Delete a node and its connected edges."""
    if not _map_in_engagement(map_id):
        return jsonify({"error": "Map not found"}), 404
    node_dao = AttackMapNodeDAO()
    existing = node_dao.find_by_id(node_id)
    if not existing or existing['map_id'] != map_id:
        return jsonify({"error": "Node not found"}), 404

    # Edges cascade via FK, but let's be explicit
    edge_dao = AttackMapEdgeDAO()
    edge_dao.delete_by_node(node_id)
    node_dao.delete(node_id)
    _touch_map(map_id)

    return jsonify({"message": "Node deleted"}), 200


@attack_maps_bp.route('/<int:map_id>/nodes/batch', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def batch_update_nodes(map_id):
    """Batch update node positions."""
    data = request.get_json()
    if not data or not isinstance(data.get('updates'), list):
        return jsonify({"error": "updates array is required"}), 400
    if not _map_in_engagement(map_id):
        return jsonify({"error": "Map not found"}), 404

    node_dao = AttackMapNodeDAO()
    count = node_dao.batch_update_positions(map_id, data['updates'])
    _touch_map(map_id)

    return jsonify({"updated": count}), 200


# ── Edge CRUD ──────────────────────────────────────────────────────

@attack_maps_bp.route('/<int:map_id>/edges', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_edge(map_id):
    """Create an edge between two nodes."""
    data = request.get_json()
    if not data or not data.get('source_node_id') or not data.get('target_node_id'):
        return jsonify({"error": "source_node_id and target_node_id are required"}), 400
    if not _map_in_engagement(map_id):
        return jsonify({"error": "Map not found"}), 404

    # Verify both nodes exist on this map
    node_dao = AttackMapNodeDAO()
    source = node_dao.find_by_id(data['source_node_id'])
    target = node_dao.find_by_id(data['target_node_id'])
    if not source or source['map_id'] != map_id:
        return jsonify({"error": "Source node not found on this map"}), 404
    if not target or target['map_id'] != map_id:
        return jsonify({"error": "Target node not found on this map"}), 404

    edge_dao = AttackMapEdgeDAO()
    edge_id = edge_dao.create({
        'map_id': map_id,
        'source_node_id': data['source_node_id'],
        'target_node_id': data['target_node_id'],
        'label': data.get('label', '')
    })
    _touch_map(map_id)

    edge = edge_dao.find_by_id(edge_id)
    return jsonify(edge), 201


@attack_maps_bp.route('/<int:map_id>/edges/<int:edge_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_edge(map_id, edge_id):
    """Delete an edge."""
    if not _map_in_engagement(map_id):
        return jsonify({"error": "Map not found"}), 404
    edge_dao = AttackMapEdgeDAO()
    existing = edge_dao.find_by_id(edge_id)
    if not existing or existing['map_id'] != map_id:
        return jsonify({"error": "Edge not found"}), 404

    edge_dao.delete(edge_id)
    _touch_map(map_id)

    return jsonify({"message": "Edge deleted"}), 200


# ── SVG Export ─────────────────────────────────────────────────────

@attack_maps_bp.route('/<int:map_id>/svg', methods=['GET'])
@require_auth
@handle_errors
def get_svg(map_id):
    """Get server-rendered SVG of the map for report embedding."""
    from utils.attack_map_svg import generate_attack_map_svg

    dao = AttackMapDAO()
    attack_map = dao.get_full_map(map_id)
    if not attack_map:
        return jsonify({"error": "Map not found"}), 404

    svg = generate_attack_map_svg(attack_map)
    return svg, 200, {'Content-Type': 'image/svg+xml'}


# ── Helpers ────────────────────────────────────────────────────────

def _map_in_engagement(map_id):
    """True if the map belongs to the active engagement (AttackMapDAO is scoped)."""
    return AttackMapDAO().find_by_id(map_id) is not None


def _touch_map(map_id):
    """Update map's updated_at timestamp."""
    try:
        cursor = g.db.cursor()
        cursor.execute(
            'UPDATE attack_maps SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (map_id,)
        )
        g.db.commit()
    except Exception as e:
        logger.warning(f"Failed to touch map {map_id}: {e}")

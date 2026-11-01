"""Evidence relationship API endpoints.

This module provides REST API endpoints for managing relationships between
evidence items and finding attack paths through the evidence graph.
"""

import logging
from flask import Blueprint, request, jsonify, g

from middleware.auth import require_auth
from models.dao.relationship_dao import RelationshipDAO, AttackPathDAO
from utils.error_handler import handle_errors

logger = logging.getLogger(__name__)

relationships_bp = Blueprint('relationships', __name__, url_prefix='/api/relationships')


@relationships_bp.route('', methods=['GET'])
@require_auth
@handle_errors
def get_all_relationships():
    """Get all relationships for active engagement.

    Returns:
        JSON with list of relationships

    Example:
        GET /api/relationships
        -> {"relationships": [...]}
    """
    dao = RelationshipDAO()
    relationships = dao.find_all(order_by='created_at DESC')

    return jsonify({"relationships": relationships}), 200


@relationships_bp.route('', methods=['POST'])
@require_auth
@handle_errors
def create_relationship():
    """Create new relationship between any nodes (evidence, findings, notes, credentials).

    Request Body:
        {
            "source_node_type": "evidence",
            "source_node_id": 123,
            "target_node_type": "finding",
            "target_node_id": 456,
            "type": "leads_to",
            "label": "Used credentials from",
            "description": "Credentials found in evidence #123 were used..."
        }

    Returns:
        JSON with created relationship ID

    Example:
        POST /api/relationships
        -> {"id": 789, "message": "Relationship created"}
    """
    data = request.get_json()

    # Validate required fields
    required = ['source_node_type', 'source_node_id', 'target_node_type', 'target_node_id', 'type']
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {', '.join(required)}"}), 400

    # Validate node types
    valid_node_types = ['evidence', 'finding', 'note', 'credential']
    if data['source_node_type'] not in valid_node_types or data['target_node_type'] not in valid_node_types:
        return jsonify({"error": f"Node type must be one of: {', '.join(valid_node_types)}"}), 400

    # Validate relationship type
    valid_types = ['leads_to', 'uses', 'discovers', 'exploits', 'escalates', 'custom']
    if data['type'] not in valid_types:
        return jsonify({"error": f"Invalid type. Must be one of: {', '.join(valid_types)}"}), 400

    try:
        dao = RelationshipDAO()
        rel_id = dao.create_relationship(
            source_node_type=data['source_node_type'],
            source_node_id=data['source_node_id'],
            target_node_type=data['target_node_type'],
            target_node_id=data['target_node_id'],
            relationship_type=data['type'],
            label=data.get('label'),
            description=data.get('description'),
            created_by=getattr(g, 'user_id', None)
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    logger.info(f"Created relationship {rel_id}: {data['source_node_type']}_{data['source_node_id']} -> {data['target_node_type']}_{data['target_node_id']}")
    return jsonify({"id": rel_id, "message": "Relationship created"}), 201


@relationships_bp.route('/<int:rel_id>', methods=['DELETE'])
@require_auth
@handle_errors
def delete_relationship(rel_id):
    """Delete relationship.

    Args:
        rel_id: Relationship ID

    Returns:
        JSON confirmation

    Example:
        DELETE /api/relationships/123
        -> {"status": "deleted"}
    """
    dao = RelationshipDAO()
    deleted = dao.delete(rel_id)

    if not deleted:
        return jsonify({"error": "Relationship not found"}), 404

    logger.info(f"Deleted relationship {rel_id}")
    return jsonify({"status": "deleted"}), 200


@relationships_bp.route('/node/<string:node_type>/<int:node_id>', methods=['GET'])
@require_auth
@handle_errors
def get_node_relationships(node_type, node_id):
    """Get all relationships for a specific node.

    Args:
        node_type: Type of node (evidence, finding, note, credential)
        node_id: Node ID

    Returns:
        JSON with relationships list

    Example:
        GET /api/relationships/node/evidence/123
        -> {"relationships": [...], "incoming": 2, "outgoing": 3}
    """
    # Validate node type
    valid_types = ['evidence', 'finding', 'note', 'credential']
    if node_type not in valid_types:
        return jsonify({"error": f"Invalid node type. Must be one of: {', '.join(valid_types)}"}), 400

    dao = RelationshipDAO()
    relationships = dao.get_relationships_for_node(node_type, node_id)

    # Count incoming vs outgoing
    incoming = sum(1 for r in relationships if r['target_node_type'] == node_type and r['target_node_id'] == node_id)
    outgoing = sum(1 for r in relationships if r['source_node_type'] == node_type and r['source_node_id'] == node_id)

    return jsonify({
        "relationships": relationships,
        "incoming": incoming,
        "outgoing": outgoing
    }), 200


@relationships_bp.route('/node/<string:node_type>/<int:node_id>', methods=['DELETE'])
@require_auth
@handle_errors
def delete_node_relationships(node_type, node_id):
    """Delete all relationships involving a node.

    Args:
        node_type: Type of node (evidence, finding, note, credential)
        node_id: Node ID

    Returns:
        JSON with count of deleted relationships

    Example:
        DELETE /api/relationships/node/evidence/123
        -> {"deleted": 5}
    """
    # Validate node type
    valid_types = ['evidence', 'finding', 'note', 'credential']
    if node_type not in valid_types:
        return jsonify({"error": f"Invalid node type. Must be one of: {', '.join(valid_types)}"}), 400

    dao = RelationshipDAO()
    count = dao.delete_by_node(node_type, node_id)

    logger.info(f"Deleted {count} relationships for {node_type} {node_id}")
    return jsonify({"deleted": count}), 200


@relationships_bp.route('/path', methods=['POST'])
@require_auth
@handle_errors
def find_attack_path():
    """Find attack path between two evidence items.

    Request Body:
        {
            "start_id": 123,
            "end_id": 456
        }

    Returns:
        JSON with path as list of evidence items with edge information

    Example:
        POST /api/relationships/path
        -> {"path": [...], "length": 3}
    """
    data = request.get_json()

    if not all(k in data for k in ['start_id', 'end_id']):
        return jsonify({"error": "start_id and end_id are required"}), 400

    dao = RelationshipDAO()
    path = dao.find_path(data['start_id'], data['end_id'])

    return jsonify({
        "path": path,
        "length": len(path)
    }), 200


@relationships_bp.route('/graph', methods=['GET'])
@require_auth
@handle_errors
def get_relationship_graph():
    """Get complete relationship graph for visualization.

    Returns:
        JSON with nodes (evidence items) and edges (relationships)

    Example:
        GET /api/relationships/graph
        -> {"nodes": [...], "edges": [...], "stats": {...}}
    """
    dao = RelationshipDAO()
    graph_data = dao.get_graph_data()
    stats = dao.get_relationship_statistics()

    return jsonify({
        "nodes": graph_data['nodes'],
        "edges": graph_data['edges'],
        "stats": stats
    }), 200


@relationships_bp.route('/stats', methods=['GET'])
@require_auth
@handle_errors
def get_relationship_stats():
    """Get relationship statistics for current engagement.

    Returns:
        JSON with relationship counts by type

    Example:
        GET /api/relationships/stats
        -> {"leads_to": 5, "uses": 3, "total": 8}
    """
    dao = RelationshipDAO()
    stats = dao.get_relationship_statistics()

    return jsonify(stats), 200


# Attack Paths endpoints

@relationships_bp.route('/paths', methods=['GET'])
@require_auth
@handle_errors
def list_attack_paths():
    """List all saved attack paths for current engagement.

    Returns:
        JSON with list of saved paths

    Example:
        GET /api/relationships/paths
        -> {"paths": [...]}
    """
    dao = AttackPathDAO()
    paths = dao.list_paths()

    return jsonify({"paths": paths}), 200


@relationships_bp.route('/paths', methods=['POST'])
@require_auth
@handle_errors
def save_attack_path():
    """Save an attack path.

    Request Body:
        {
            "name": "Initial Access to Domain Admin",
            "description": "Path from phishing to DA",
            "start_id": 123,
            "end_id": 456,
            "path_data": [...]
        }

    Returns:
        JSON with saved path ID

    Example:
        POST /api/relationships/paths
        -> {"id": 789, "message": "Attack path saved"}
    """
    data = request.get_json()

    if not all(k in data for k in ['name', 'start_id', 'end_id', 'path_data']):
        return jsonify({"error": "name, start_id, end_id, and path_data are required"}), 400

    dao = AttackPathDAO()
    path_id = dao.save_path(
        name=data['name'],
        start_id=data['start_id'],
        end_id=data['end_id'],
        path_data=data['path_data'],
        description=data.get('description'),
        created_by=getattr(g, 'user_id', None)
    )

    logger.info(f"Saved attack path '{data['name']}' with id {path_id}")
    return jsonify({"id": path_id, "message": "Attack path saved"}), 201


@relationships_bp.route('/paths/<int:path_id>', methods=['GET'])
@require_auth
@handle_errors
def get_attack_path(path_id):
    """Get saved attack path details.

    Args:
        path_id: Path ID

    Returns:
        JSON with path details including full path data

    Example:
        GET /api/relationships/paths/123
        -> {"id": 123, "name": "...", "path_data": [...]}
    """
    dao = AttackPathDAO()
    path = dao.get_path(path_id)

    if not path:
        return jsonify({"error": "Attack path not found"}), 404

    return jsonify(path), 200


@relationships_bp.route('/paths/<int:path_id>', methods=['DELETE'])
@require_auth
@handle_errors
def delete_attack_path(path_id):
    """Delete saved attack path.

    Args:
        path_id: Path ID

    Returns:
        JSON confirmation

    Example:
        DELETE /api/relationships/paths/123
        -> {"status": "deleted"}
    """
    dao = AttackPathDAO()
    deleted = dao.delete(path_id)

    if not deleted:
        return jsonify({"error": "Attack path not found"}), 404

    logger.info(f"Deleted attack path {path_id}")
    return jsonify({"status": "deleted"}), 200

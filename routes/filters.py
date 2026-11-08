"""Saved filter routes for PTVault."""

from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth, require_engagement_access
from routes.engagements import require_active_engagement
from utils.error_handler import (
    handle_errors,
    ValidationError,
    DatabaseError,
    NotFoundError,
    require_fields,
)
import json
import ipaddress

filters_bp = Blueprint('filters', __name__, url_prefix='/api/filters')


def validate_cidr(cidr_str):
    """
    Validate CIDR notation or single IP address.

    Args:
        cidr_str: CIDR notation (e.g., "192.168.1.0/24") or single IP

    Raises:
        ValidationError: If CIDR notation is invalid
    """
    try:
        # This will handle both single IPs and CIDR notation
        ipaddress.ip_network(cidr_str, strict=False)
    except ValueError as e:
        raise ValidationError(f"Invalid CIDR notation: {str(e)}")


def ip_in_cidr(ip_str, cidr_str):
    """
    Check if an IP address is within a CIDR range.

    Args:
        ip_str: IP address to check (e.g., "192.168.1.10")
        cidr_str: CIDR notation (e.g., "192.168.1.0/24") or single IP

    Returns:
        bool: True if IP is in the CIDR range, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        network = ipaddress.ip_network(cidr_str, strict=False)
        return ip in network
    except ValueError:
        return False


def validate_filter_json(filter_json):
    """
    Validate filter JSON structure.

    Expected structure:
    {
        "search_query": str (optional),
        "tags": list[str] (optional),
        "evidence_type": str (optional),
        "severity": str (optional),
        "tool": str (optional),
        "host_id": int (optional),
        "indicators": list[str] (optional),
        "cidr": str (optional)
    }
    """
    if not isinstance(filter_json, dict):
        raise ValidationError("filter_json must be an object")

    # Validate optional fields
    if 'search_query' in filter_json and not isinstance(filter_json['search_query'], str):
        raise ValidationError("search_query must be a string")

    if 'tags' in filter_json:
        if not isinstance(filter_json['tags'], list):
            raise ValidationError("tags must be an array")
        if not all(isinstance(t, str) for t in filter_json['tags']):
            raise ValidationError("all tags must be strings")

    if 'evidence_type' in filter_json and not isinstance(filter_json['evidence_type'], str):
        raise ValidationError("evidence_type must be a string")

    if 'severity' in filter_json and not isinstance(filter_json['severity'], str):
        raise ValidationError("severity must be a string")

    if 'tool' in filter_json and not isinstance(filter_json['tool'], str):
        raise ValidationError("tool must be a string")

    if 'host_id' in filter_json:
        if not isinstance(filter_json['host_id'], int):
            raise ValidationError("host_id must be an integer")

    if 'indicators' in filter_json:
        if not isinstance(filter_json['indicators'], list):
            raise ValidationError("indicators must be an array")
        if not all(isinstance(i, str) for i in filter_json['indicators']):
            raise ValidationError("all indicators must be strings")

    if 'cidr' in filter_json:
        if not isinstance(filter_json['cidr'], str):
            raise ValidationError("cidr must be a string")
        # Validate CIDR notation
        validate_cidr(filter_json['cidr'])


def row_to_dict(row):
    """Convert database row to filter dictionary."""
    return {
        'id': row[0],
        'engagement_id': row[1],
        'name': row[2],
        'description': row[3],
        'filter_json': json.loads(row[4]),
        'created_at': row[5]
    }


@filters_bp.route('', methods=['GET'])
@require_auth
@require_active_engagement
@handle_errors
def list_filters():
    """
    List all saved filters for the active engagement.
    """
    engagement_id = g.active_engagement_id

    try:
        cursor = g.db.cursor()
        cursor.execute('''
            SELECT id, engagement_id, name, description, filter_json, created_at
            FROM saved_filters
            WHERE engagement_id = ?
            ORDER BY created_at DESC
        ''', (engagement_id,))

        rows = cursor.fetchall()
        filters = [row_to_dict(row) for row in rows]

        return jsonify(filters), 200

    except Exception as e:
        raise DatabaseError(f"Failed to fetch saved filters: {str(e)}")


@filters_bp.route('', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
@handle_errors
def create_filter():
    """
    Create a new saved filter.

    Request body:
    {
        "name": "Filter name (required)",
        "description": "Optional description",
        "filter_json": {
            "search_query": "optional search text",
            "tags": ["tag1", "tag2"],
            "evidence_type": "screenshot",
            "severity": "critical",
            "tool": "burp",
            "host_id": 5
        }
    }
    """
    data = request.get_json()
    require_fields(data, ['name', 'filter_json'])

    engagement_id = g.active_engagement_id
    name = data['name'].strip()
    description = data.get('description', '').strip() or None
    filter_json = data['filter_json']

    if not name:
        raise ValidationError("Filter name cannot be empty")

    # Validate filter structure
    validate_filter_json(filter_json)

    try:
        cursor = g.db.cursor()
        cursor.execute('''
            INSERT INTO saved_filters (engagement_id, name, description, filter_json)
            VALUES (?, ?, ?, ?)
        ''', (engagement_id, name, description, json.dumps(filter_json)))

        g.db.commit()
        filter_id = cursor.lastrowid

        # Fetch the created filter
        cursor.execute('''
            SELECT id, engagement_id, name, description, filter_json, created_at
            FROM saved_filters
            WHERE id = ?
        ''', (filter_id,))

        row = cursor.fetchone()
        if not row:
            raise DatabaseError("Failed to retrieve created filter")

        return jsonify(row_to_dict(row)), 201

    except Exception as e:
        g.db.rollback()
        raise DatabaseError(f"Failed to create saved filter: {str(e)}")


@filters_bp.route('/<int:filter_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
@handle_errors
def update_filter(filter_id):
    """
    Update a saved filter.

    Request body (all fields optional):
    {
        "name": "New name",
        "description": "New description",
        "filter_json": { ... }
    }
    """
    data = request.get_json()
    engagement_id = g.active_engagement_id

    # Check that filter exists and belongs to engagement
    try:
        cursor = g.db.cursor()
        cursor.execute('''
            SELECT id, engagement_id FROM saved_filters
            WHERE id = ?
        ''', (filter_id,))

        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Saved filter {filter_id} not found")

        if row[1] != engagement_id:
            raise ValidationError("Cannot modify filter from different engagement")

        # Build update query
        updates = []
        params = []

        if 'name' in data:
            name = data['name'].strip()
            if not name:
                raise ValidationError("Filter name cannot be empty")
            updates.append("name = ?")
            params.append(name)

        if 'description' in data:
            description = data['description'].strip() or None
            updates.append("description = ?")
            params.append(description)

        if 'filter_json' in data:
            filter_json = data['filter_json']
            validate_filter_json(filter_json)
            updates.append("filter_json = ?")
            params.append(json.dumps(filter_json))

        if not updates:
            raise ValidationError("No fields to update")

        # Execute update
        params.append(filter_id)
        cursor.execute(f'''
            UPDATE saved_filters
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)

        g.db.commit()

        # Fetch updated filter
        cursor.execute('''
            SELECT id, engagement_id, name, description, filter_json, created_at
            FROM saved_filters
            WHERE id = ?
        ''', (filter_id,))

        row = cursor.fetchone()
        if not row:
            raise DatabaseError("Failed to retrieve updated filter")

        return jsonify(row_to_dict(row)), 200

    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        g.db.rollback()
        raise DatabaseError(f"Failed to update saved filter: {str(e)}")


@filters_bp.route('/<int:filter_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
@handle_errors
def delete_filter(filter_id):
    """
    Delete a saved filter.
    """
    engagement_id = g.active_engagement_id

    try:
        cursor = g.db.cursor()

        # Check that filter exists and belongs to engagement
        cursor.execute('''
            SELECT id, engagement_id FROM saved_filters
            WHERE id = ?
        ''', (filter_id,))

        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Saved filter {filter_id} not found")

        if row[1] != engagement_id:
            raise ValidationError("Cannot delete filter from different engagement")

        # Delete filter
        cursor.execute('DELETE FROM saved_filters WHERE id = ?', (filter_id,))
        g.db.commit()

        return jsonify({"message": "Filter deleted"}), 200

    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        g.db.rollback()
        raise DatabaseError(f"Failed to delete saved filter: {str(e)}")


@filters_bp.route('/<int:filter_id>/apply', methods=['POST'])
@require_auth
@require_active_engagement
@handle_errors
def apply_filter(filter_id):
    """
    Apply a saved filter and return matching evidence.

    This is a convenience endpoint that retrieves the filter and applies it
    to the evidence search/list endpoint.

    Returns the same format as GET /api/evidence (with filters applied).
    """
    engagement_id = g.active_engagement_id

    try:
        cursor = g.db.cursor()

        # Fetch the filter
        cursor.execute('''
            SELECT id, engagement_id, filter_json FROM saved_filters
            WHERE id = ?
        ''', (filter_id,))

        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Saved filter {filter_id} not found")

        if row[1] != engagement_id:
            raise ValidationError("Cannot apply filter from different engagement")

        filter_json = json.loads(row[2])

        # Build evidence query based on filter
        query = "SELECT * FROM evidence WHERE engagement_id = ?"
        params = [engagement_id]

        # Apply filters
        if 'evidence_type' in filter_json:
            query += " AND evidence_type = ?"
            params.append(filter_json['evidence_type'])

        if 'tags' in filter_json and filter_json['tags']:
            # Tags filter (AND logic - evidence must have all tags)
            for tag in filter_json['tags']:
                query += " AND (tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)"
                params.extend([
                    f"{tag},%",  # tag at start
                    f"%,{tag},%",  # tag in middle
                    f"%,{tag}",  # tag at end
                    tag  # tag only
                ])

        if 'host_id' in filter_json:
            # Filter by host
            query = f"""
                SELECT e.* FROM evidence e
                JOIN evidence_hosts eh ON e.id = eh.evidence_id
                WHERE e.engagement_id = ? AND eh.host_id = ?
            """
            params = [engagement_id, filter_json['host_id']]

        # Note: search_query, severity, and tool require metadata parsing
        # These are handled in the frontend by filtering results after retrieval

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Convert to dictionaries
        evidence_list = []
        for row in rows:
            evidence = {
                'id': row[0],
                'engagement_id': row[1],
                'evidence_type': row[2],
                'title': row[3],
                'content': row[4],
                'tags': row[5],
                'file_path': row[6],
                'file_name': row[7],
                'file_size': row[8],
                'metadata': row[9],
                'created_at': row[10],
                'updated_at': row[11]
            }

            # Apply metadata filters if needed
            apply_item = True

            if 'severity' in filter_json or 'tool' in filter_json:
                metadata = {}
                if evidence['metadata']:
                    try:
                        metadata = json.loads(evidence['metadata'])
                    except:
                        pass

                # Check severity filter
                if 'severity' in filter_json:
                    evidence_severity = metadata.get('severity_level', '').lower()
                    if evidence_severity != filter_json['severity'].lower():
                        apply_item = False

                # Check tool filter
                if 'tool' in filter_json:
                    evidence_tool = metadata.get('tool_name', '').lower()
                    if evidence_tool != filter_json['tool'].lower():
                        apply_item = False

            # Apply search query filter (simple contains check)
            if 'search_query' in filter_json and filter_json['search_query']:
                query_lower = filter_json['search_query'].lower()
                searchable_text = f"{evidence['title']} {evidence['content']}".lower()
                if query_lower not in searchable_text:
                    apply_item = False

            if apply_item:
                evidence_list.append(evidence)

        return jsonify(evidence_list), 200

    except (NotFoundError, ValidationError):
        raise
    except Exception as e:
        raise DatabaseError(f"Failed to apply saved filter: {str(e)}")

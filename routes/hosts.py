"""Host management routes for PTVault."""

import logging

from flask import Blueprint, request, jsonify, g, session
from middleware.auth import require_auth, require_engagement_access
from models.database import run_migrations
from utils.audit_logger import audit_view
from utils.error_handler import handle_errors
from utils.host_extractor import (
    get_hosts_for_engagement,
    get_evidence_without_hosts,
    get_or_create_host,
    link_evidence_to_host,
    unlink_evidence_from_host
)

logger = logging.getLogger(__name__)

hosts_bp = Blueprint('hosts', __name__, url_prefix='/api/hosts')

# Flag to track if migration has been attempted
_migration_attempted = False


def require_active_engagement():
    """Get active engagement ID or return error response."""
    active_id = session.get('active_engagement_id')
    if not active_id:
        return None, (jsonify({"error": "No active engagement selected"}), 400)
    return active_id, None


@hosts_bp.route('', methods=['GET'])
@require_auth
@handle_errors
def list_hosts():
    """
    List all hosts for the active engagement with evidence counts.
    Also returns count of evidence without hosts (for "General" section).
    """
    global _migration_attempted

    engagement_id, error = require_active_engagement()
    if error:
        return error

    try:
        logger.debug("list_hosts: engagement_id=%d", engagement_id)
        hosts = get_hosts_for_engagement(engagement_id, g.db)
        general_count = get_evidence_without_hosts(engagement_id, g.db)
        logger.debug("list_hosts: found %d hosts, general_count=%d", len(hosts), general_count)

        return jsonify({
            "hosts": hosts,
            "general_count": general_count
        }), 200

    except Exception as e:
        error_msg = str(e)
        # Check if error is due to missing columns (migration needed)
        if not _migration_attempted and ('no such column' in error_msg.lower() or 'no column' in error_msg.lower()):
            _migration_attempted = True
            logger.info("Detected missing columns, running migrations...")
            try:
                cursor = g.db.cursor()
                from models.database import migrate_host_indicators
                migrate_host_indicators(cursor)
                g.db.commit()
                logger.info("Migration completed successfully")

                # Retry the request
                hosts = get_hosts_for_engagement(engagement_id, g.db)
                general_count = get_evidence_without_hosts(engagement_id, g.db)
                return jsonify({
                    "hosts": hosts,
                    "general_count": general_count
                }), 200
            except Exception as migration_error:
                logger.error("Migration failed: %s", migration_error)
                return jsonify({"error": f"Migration failed: {str(migration_error)}"}), 500

        return jsonify({"error": str(e)}), 500


@hosts_bp.route('/search', methods=['GET'])
@require_auth
@handle_errors
def search_hosts():
    """Search hosts by keyword across notes, evidence, ports, credentials, and scan metadata."""
    import json as _json

    engagement_id, error = require_active_engagement()
    if error:
        return error

    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'host_ids': []}), 200

    cursor = g.db.cursor()
    like_pattern = f'%{q}%'
    q_lower = q.lower()

    # Phase 1: Direct table search (host_notes, evidence_hosts links, ports, creds)
    cursor.execute('''
        SELECT DISTINCT h.id FROM hosts h
        LEFT JOIN host_notes hn ON h.id = hn.host_id
        LEFT JOIN evidence_hosts eh ON h.id = eh.host_id
        LEFT JOIN evidence e ON eh.evidence_id = e.id
        LEFT JOIN host_ports hp ON h.id = hp.host_id
        LEFT JOIN host_credentials hc ON h.id = hc.host_id
        WHERE h.engagement_id = ?
          AND (
            h.ip LIKE ? OR h.hostname LIKE ?
            OR hn.content LIKE ?
            OR e.title LIKE ? OR e.content LIKE ?
            OR e.metadata LIKE ? OR e.tags LIKE ?
            OR hp.service LIKE ? OR hp.version LIKE ?
            OR hc.username LIKE ? OR hc.service LIKE ? OR hc.notes LIKE ?
          )
    ''', (engagement_id, *([like_pattern] * 12)))

    matched_ids = set(row[0] for row in cursor.fetchall())

    # Phase 2: Search inside scan metadata JSON (Nessus, Nmap, etc.)
    # Scan evidence stores per-host data in metadata.hosts[].vulnerabilities[]
    # which isn't linked via evidence_hosts, so we parse it here.
    cursor.execute('''
        SELECT metadata FROM evidence
        WHERE engagement_id = ? AND metadata LIKE ?
    ''', (engagement_id, like_pattern))

    # Build IP-to-host-id lookup for this engagement
    ip_to_id = None
    for (metadata_str,) in cursor.fetchall():
        try:
            metadata = _json.loads(metadata_str)
        except (ValueError, TypeError):
            continue

        hosts_data = metadata.get('hosts')
        if not isinstance(hosts_data, list):
            continue

        # Lazily build the IP lookup
        if ip_to_id is None:
            cursor2 = g.db.cursor()
            cursor2.execute(
                'SELECT id, ip FROM hosts WHERE engagement_id = ?',
                (engagement_id,)
            )
            ip_to_id = {row[1]: row[0] for row in cursor2.fetchall()}

        for host_entry in hosts_data:
            host_ip = host_entry.get('ip', '')
            if host_ip not in ip_to_id:
                continue
            host_id = ip_to_id[host_ip]
            if host_id in matched_ids:
                continue

            # Search vulnerability/finding fields for this host
            for vuln in host_entry.get('vulnerabilities', []):
                searchable = ' '.join(
                    str(vuln.get(f) or '') for f in (
                        'plugin_name', 'name', 'description', 'synopsis',
                        'solution', 'plugin_output', 'plugin_family',
                        'service', 'risk_factor', 'cves',
                    )
                ).lower()
                if q_lower in searchable:
                    matched_ids.add(host_id)
                    break

    return jsonify({'host_ids': list(matched_ids)}), 200


@hosts_bp.route('/<int:host_id>', methods=['GET'])
@require_auth
@handle_errors
def get_host(host_id):
    """Get a single host by ID with its evidence."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Get host
    cursor.execute('''
        SELECT id, engagement_id, ip, hostname, os, notes,
               rooted, shell, interested, not_interested, out_of_scope, flagged, reviewed, color_category,
               created_at, updated_at
        FROM hosts
        WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Host not found"}), 404

    host = {
        "id": row[0],
        "engagement_id": row[1],
        "ip": row[2],
        "hostname": row[3],
        "os": row[4],
        "notes": row[5],
        "rooted": bool(row[6]),
        "shell": bool(row[7]),
        "interested": bool(row[8]),
        "not_interested": bool(row[9]),
        "out_of_scope": bool(row[10]),
        "flagged": bool(row[11]),
        "reviewed": bool(row[12]),
        "color_category": row[13],
        "created_at": row[14],
        "updated_at": row[15]
    }

    # Get evidence linked to this host
    cursor.execute('''
        SELECT
            e.id, e.evidence_type, e.title, e.content,
            e.file_name, e.created_at, e.tool_name, e.severity_level,
            eh.source
        FROM evidence e
        JOIN evidence_hosts eh ON e.id = eh.evidence_id
        WHERE eh.host_id = ?
        ORDER BY e.created_at DESC
    ''', (host_id,))

    evidence = []
    for ev_row in cursor.fetchall():
        evidence.append({
            "id": ev_row[0],
            "evidence_type": ev_row[1],
            "title": ev_row[2],
            "content": ev_row[3],
            "file_name": ev_row[4],
            "created_at": ev_row[5],
            "tool_name": ev_row[6],
            "severity_level": ev_row[7],
            "link_source": ev_row[8]
        })

    host["evidence"] = evidence
    host["evidence_count"] = len(evidence)

    return jsonify(host), 200


@hosts_bp.route('', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_host():
    """
    Create a new host manually.
    Required: ip
    Optional: hostname, os, notes
    """
    engagement_id, error = require_active_engagement()
    if error:
        return error

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    ip = data.get('ip')
    if not ip:
        return jsonify({"error": "ip is required"}), 400

    hostname = data.get('hostname')
    os_info = data.get('os')
    notes = data.get('notes')

    cursor = g.db.cursor()

    # Check if host already exists
    cursor.execute('''
        SELECT id FROM hosts
        WHERE engagement_id = ? AND ip = ?
    ''', (engagement_id, ip))

    existing = cursor.fetchone()
    if existing:
        return jsonify({"error": "Host with this IP already exists", "host_id": existing[0]}), 409

    # Create host
    cursor.execute('''
        INSERT INTO hosts (engagement_id, ip, hostname, os, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (engagement_id, ip, hostname, os_info, notes))
    g.db.commit()
    host_id = cursor.lastrowid

    return jsonify({
        "id": host_id,
        "engagement_id": engagement_id,
        "ip": ip,
        "hostname": hostname,
        "os": os_info,
        "notes": notes
    }), 201


@hosts_bp.route('/<int:host_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def update_host(host_id):
    """Update host details (hostname, os, notes)."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    cursor = g.db.cursor()

    # Check host exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts
        WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))

    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Build dynamic update
    update_fields = []
    update_values = []

    # Text fields
    for field in ['hostname', 'os', 'notes', 'color_category']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    # Boolean indicator fields (stored as INTEGER)
    for field in ['rooted', 'shell', 'interested', 'not_interested', 'out_of_scope', 'flagged', 'reviewed']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(1 if data[field] else 0)

    if not update_fields:
        return jsonify({"error": "No fields to update"}), 400

    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(host_id)

    query = f"UPDATE hosts SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch updated host
    cursor.execute('''
        SELECT id, engagement_id, ip, hostname, os, notes,
               rooted, shell, interested, not_interested, out_of_scope, flagged, reviewed, color_category,
               created_at, updated_at
        FROM hosts WHERE id = ?
    ''', (host_id,))
    row = cursor.fetchone()

    return jsonify({
        "id": row[0],
        "engagement_id": row[1],
        "ip": row[2],
        "hostname": row[3],
        "os": row[4],
        "notes": row[5],
        "rooted": bool(row[6]),
        "shell": bool(row[7]),
        "interested": bool(row[8]),
        "not_interested": bool(row[9]),
        "out_of_scope": bool(row[10]),
        "flagged": bool(row[11]),
        "reviewed": bool(row[12]),
        "color_category": row[13],
        "created_at": row[14],
        "updated_at": row[15]
    }), 200


@hosts_bp.route('/<int:host_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_host(host_id):
    """Delete a host. This unlinks all evidence from this host but doesn't delete the evidence."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Check host exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts
        WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))

    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Delete host (cascade will remove evidence_hosts links)
    cursor.execute('DELETE FROM hosts WHERE id = ?', (host_id,))
    g.db.commit()

    return '', 204


@hosts_bp.route('/<int:host_id>/evidence', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def link_evidence(host_id):
    """
    Link evidence to a host.
    Body: { "evidence_id": 123 }
    """
    engagement_id, error = require_active_engagement()
    if error:
        return error

    data = request.get_json()
    if not data or 'evidence_id' not in data:
        return jsonify({"error": "evidence_id required"}), 400

    evidence_id = data['evidence_id']

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts
        WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Verify evidence belongs to engagement
    cursor.execute('''
        SELECT id FROM evidence
        WHERE id = ? AND engagement_id = ?
    ''', (evidence_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Evidence not found"}), 404

    # Link them
    if link_evidence_to_host(evidence_id, host_id, source='manual', conn=g.db):
        g.db.commit()
        return jsonify({"status": "linked"}), 200
    else:
        return jsonify({"error": "Failed to link"}), 500


@hosts_bp.route('/<int:host_id>/evidence/<int:evidence_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def unlink_evidence(host_id, evidence_id):
    """Unlink evidence from a host."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts
        WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Unlink
    if unlink_evidence_from_host(evidence_id, host_id, conn=g.db):
        g.db.commit()
        return '', 204
    else:
        return jsonify({"error": "Failed to unlink"}), 500


# ============================================
# HOST NOTES ENDPOINTS
# ============================================

def _host_note_dao():
    """Build a NoteTreeDAO bound to host_notes."""
    from models.dao.note_tree_dao import NoteTreeDAO
    return NoteTreeDAO('host_notes', 'host_id')


def _verify_host_in_engagement(host_id, engagement_id):
    cursor = g.db.cursor()
    cursor.execute(
        "SELECT id FROM hosts WHERE id = ? AND engagement_id = ?",
        (host_id, engagement_id),
    )
    return cursor.fetchone() is not None


@hosts_bp.route('/<int:host_id>/notes', methods=['GET'])
@require_auth
@handle_errors
def list_notes(host_id):
    """Get all notes for a host (flat list for tree-build)."""
    engagement_id, error = require_active_engagement()
    if error:
        return error
    if not _verify_host_in_engagement(host_id, engagement_id):
        return jsonify({"error": "Host not found"}), 404

    notes = _host_note_dao().list_for(host_id)
    return jsonify({"notes": notes}), 200


@hosts_bp.route('/<int:host_id>/notes/<int:note_id>', methods=['GET'])
@require_auth
@handle_errors
def get_note(host_id, note_id):
    """Get full content for a single host note (lazy-load companion)."""
    engagement_id, error = require_active_engagement()
    if error:
        return error
    if not _verify_host_in_engagement(host_id, engagement_id):
        return jsonify({"error": "Host not found"}), 404

    note = _host_note_dao().get_full(note_id, host_id)
    if not note:
        return jsonify({"error": "Note not found"}), 404
    return jsonify(note), 200


@hosts_bp.route('/<int:host_id>/notes', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_note(host_id):
    """Create a new note for a host.

    Optional body fields:
      parent_id (int|null): nest under another note for the same host
      sort_order (int): explicit ordering; defaults to max+1 within parent
    """
    engagement_id, error = require_active_engagement()
    if error:
        return error
    if not _verify_host_in_engagement(host_id, engagement_id):
        return jsonify({"error": "Host not found"}), 404

    data = request.get_json() or {}
    content = data.get('content', '')
    title = data.get('title', 'New note')

    parent_id = data.get('parent_id')
    sort_order = data.get('sort_order')

    dao = _host_note_dao()
    if not dao.parent_belongs_to_scope(parent_id, host_id):
        return jsonify({"error": "parent note not found for this host"}), 400

    note_id = dao.create(host_id, content, title=title, parent_id=parent_id, sort_order=sort_order)
    return jsonify(dao.get_full(note_id, host_id)), 201


@hosts_bp.route('/<int:host_id>/notes/<int:note_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def update_note(host_id, note_id):
    """Update a host note's content."""
    engagement_id, error = require_active_engagement()
    if error:
        return error
    if not _verify_host_in_engagement(host_id, engagement_id):
        return jsonify({"error": "Host not found"}), 404

    data = request.get_json() or {}
    content = data.get('content')
    title = data.get('title')

    if content is None and title is None:
        return jsonify({"error": "content or title is required"}), 400

    dao = _host_note_dao()
    note = dao.get_full(note_id, host_id)
    if not note:
        return jsonify({"error": "Note not found"}), 404

    new_content = content if content is not None else note['content']
    new_title = title if title is not None else note.get('title', '')
    if not dao.update(note_id, host_id, new_content, new_title):
        return jsonify({"error": "Note not found"}), 404
    return jsonify(dao.get_full(note_id, host_id)), 200


@hosts_bp.route('/<int:host_id>/notes/<int:note_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_note(host_id, note_id):
    """Delete a host note. Blocked when it has children."""
    engagement_id, error = require_active_engagement()
    if error:
        return error
    if not _verify_host_in_engagement(host_id, engagement_id):
        return jsonify({"error": "Host not found"}), 404

    dao = _host_note_dao()
    if not dao.get_full(note_id, host_id):
        return jsonify({"error": "Note not found"}), 404

    child_count = dao.count_children(note_id, host_id)
    if child_count > 0:
        return jsonify({
            "error": (
                f"This note has {child_count} child note(s). "
                "Delete or move them first."
            ),
            "child_count": child_count,
        }), 409

    dao.delete(note_id, host_id)
    return '', 204


@hosts_bp.route('/<int:host_id>/notes/<int:note_id>/move', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def move_note(host_id, note_id):
    """Move/reorder a host note within the tree.

    Body: { "parent_id": int|null, "sort_order": int|null }
    """
    engagement_id, error = require_active_engagement()
    if error:
        return error
    if not _verify_host_in_engagement(host_id, engagement_id):
        return jsonify({"error": "Host not found"}), 404

    data = request.get_json() or {}
    parent_id = data.get('parent_id')
    sort_order = data.get('sort_order')

    dao = _host_note_dao()
    if not dao.get_full(note_id, host_id):
        return jsonify({"error": "Note not found"}), 404

    try:
        dao.move(note_id, host_id, parent_id, sort_order)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(dao.get_full(note_id, host_id)), 200


# ============================================
# HOST PORTS ENDPOINTS
# ============================================

@hosts_bp.route('/<int:host_id>/ports', methods=['GET'])
@require_auth
@handle_errors
def list_ports(host_id):
    """Get all ports for a host."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    cursor.execute('''
        SELECT id, host_id, port, protocol, state, service, version, source, evidence_id, created_at, updated_at
        FROM host_ports
        WHERE host_id = ?
        ORDER BY port ASC
    ''', (host_id,))

    ports = []
    for row in cursor.fetchall():
        ports.append({
            "id": row[0],
            "host_id": row[1],
            "port": row[2],
            "protocol": row[3],
            "state": row[4],
            "service": row[5],
            "version": row[6],
            "source": row[7],
            "evidence_id": row[8],
            "created_at": row[9],
            "updated_at": row[10]
        })

    return jsonify({"ports": ports}), 200


@hosts_bp.route('/<int:host_id>/ports', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_port(host_id):
    """Create a new port entry for a host."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    data = request.get_json()
    if not data or 'port' not in data:
        return jsonify({"error": "port is required"}), 400

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    port_num = data['port']
    protocol = data.get('protocol', 'tcp')
    state = data.get('state', 'open')
    service = data.get('service')
    version = data.get('version')

    try:
        cursor.execute('''
            INSERT INTO host_ports (host_id, port, protocol, state, service, version, source)
            VALUES (?, ?, ?, ?, ?, ?, 'manual')
        ''', (host_id, port_num, protocol, state, service, version))
        g.db.commit()
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({"error": "Port already exists for this host"}), 409
        raise

    port_id = cursor.lastrowid

    return jsonify({
        "id": port_id,
        "host_id": host_id,
        "port": port_num,
        "protocol": protocol,
        "state": state,
        "service": service,
        "version": version,
        "source": "manual"
    }), 201


@hosts_bp.route('/<int:host_id>/ports/<int:port_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def update_port(host_id, port_id):
    """Update a port entry."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Verify port belongs to host
    cursor.execute('''
        SELECT id FROM host_ports WHERE id = ? AND host_id = ?
    ''', (port_id, host_id))
    if not cursor.fetchone():
        return jsonify({"error": "Port not found"}), 404

    # Build dynamic update
    update_fields = []
    update_values = []

    for field in ['state', 'service', 'version']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if not update_fields:
        return jsonify({"error": "No fields to update"}), 400

    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(port_id)

    query = f"UPDATE host_ports SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch updated port
    cursor.execute('''
        SELECT id, host_id, port, protocol, state, service, version, source, evidence_id, created_at, updated_at
        FROM host_ports WHERE id = ?
    ''', (port_id,))
    row = cursor.fetchone()

    return jsonify({
        "id": row[0],
        "host_id": row[1],
        "port": row[2],
        "protocol": row[3],
        "state": row[4],
        "service": row[5],
        "version": row[6],
        "source": row[7],
        "evidence_id": row[8],
        "created_at": row[9],
        "updated_at": row[10]
    }), 200


@hosts_bp.route('/<int:host_id>/ports/<int:port_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_port(host_id, port_id):
    """Delete a port entry."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Verify port belongs to host
    cursor.execute('''
        SELECT id FROM host_ports WHERE id = ? AND host_id = ?
    ''', (port_id, host_id))
    if not cursor.fetchone():
        return jsonify({"error": "Port not found"}), 404

    cursor.execute('DELETE FROM host_ports WHERE id = ?', (port_id,))
    g.db.commit()

    return '', 204


# ============================================
# PORT GRID ENDPOINT (Bulk port data)
# ============================================

@hosts_bp.route('/port-grid', methods=['GET'])
@require_auth
@handle_errors
def get_port_grid():
    """Get all port data for the engagement in a single request for the port grid view."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Get all hosts for the engagement
    cursor.execute('''
        SELECT id, ip, hostname
        FROM hosts
        WHERE engagement_id = ?
        ORDER BY ip ASC
    ''', (engagement_id,))

    hosts = []
    host_ids = []
    for row in cursor.fetchall():
        hosts.append({
            "id": row[0],
            "ip": row[1],
            "hostname": row[2]
        })
        host_ids.append(row[0])

    if not host_ids:
        return jsonify({"hosts": [], "ports": []}), 200

    # Get all ports for all hosts in one query
    placeholders = ','.join('?' * len(host_ids))
    cursor.execute(f'''
        SELECT host_id, port, protocol, state, service
        FROM host_ports
        WHERE host_id IN ({placeholders})
        ORDER BY port ASC
    ''', host_ids)

    # Build port map: port/protocol -> { port, protocol, service, hosts: { hostId: state } }
    port_map = {}
    for row in cursor.fetchall():
        host_id, port, protocol, state, service = row
        port_key = f"{port}/{protocol}"

        if port_key not in port_map:
            port_map[port_key] = {
                "port": port,
                "protocol": protocol,
                "service": service or "",
                "hosts": {}
            }

        port_map[port_key]["hosts"][host_id] = state

        # Update service name if we have a better one
        if service and not port_map[port_key]["service"]:
            port_map[port_key]["service"] = service

    # Sort ports by port number
    sorted_ports = sorted(port_map.values(), key=lambda p: p["port"])

    return jsonify({
        "hosts": hosts,
        "ports": sorted_ports
    }), 200


# ============================================
# HOST CREDENTIALS ENDPOINTS
# ============================================

@hosts_bp.route('/<int:host_id>/credentials', methods=['GET'])
@require_auth
@handle_errors
def list_credentials(host_id):
    """Get all credentials for a host."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    cursor.execute('''
        SELECT id, host_id, username, password, password_type, hash_type, service, notes, created_at, updated_at
        FROM host_credentials
        WHERE host_id = ?
        ORDER BY created_at DESC
    ''', (host_id,))

    credentials = []
    for row in cursor.fetchall():
        credentials.append({
            "id": row[0],
            "host_id": row[1],
            "username": row[2],
            "password": None,  # masked; reveal via .../secret (M-9)
            "has_secret": bool(row[3]),
            "password_type": row[4],
            "hash_type": row[5],
            "service": row[6],
            "notes": row[7],
            "created_at": row[8],
            "updated_at": row[9]
        })

    return jsonify({"credentials": credentials}), 200


@hosts_bp.route('/<int:host_id>/credentials/<int:cred_id>/secret', methods=['GET'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def reveal_credential(host_id, cred_id):
    """Return one host credential's password or hash. Editors and above; every reveal is audited."""
    row = g.db.execute(
        '''SELECT hc.password FROM host_credentials hc
           JOIN hosts h ON hc.host_id = h.id
           WHERE hc.id = ? AND hc.host_id = ? AND h.engagement_id = ?''',
        (cred_id, host_id, g.active_engagement_id)
    ).fetchone()
    if not row:
        return jsonify({"error": "credential not found"}), 404
    audit_view('host_credential', cred_id, engagement_id=g.active_engagement_id, field='password')
    return jsonify({"secret": row[0]}), 200


@hosts_bp.route('/<int:host_id>/credentials', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_credential(host_id):
    """Create a new credential entry for a host."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    username = data.get('username')
    password = data.get('password')
    password_type = data.get('password_type', 'cleartext')
    hash_type = data.get('hash_type') if password_type == 'hash' else None
    service = data.get('service')
    notes = data.get('notes')

    cursor.execute('''
        INSERT INTO host_credentials (host_id, username, password, password_type, hash_type, service, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (host_id, username, password, password_type, hash_type, service, notes))
    g.db.commit()
    cred_id = cursor.lastrowid

    return jsonify({
        "id": cred_id,
        "host_id": host_id,
        "username": username,
        "password": None,  # masked; reveal via .../secret (M-9)
        "has_secret": bool(password),
        "password_type": password_type,
        "hash_type": hash_type,
        "service": service,
        "notes": notes
    }), 201


@hosts_bp.route('/<int:host_id>/credentials/<int:cred_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def update_credential(host_id, cred_id):
    """Update a credential entry."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Verify credential belongs to host
    cursor.execute('''
        SELECT id FROM host_credentials WHERE id = ? AND host_id = ?
    ''', (cred_id, host_id))
    if not cursor.fetchone():
        return jsonify({"error": "Credential not found"}), 404

    # Build dynamic update
    update_fields = []
    update_values = []

    for field in ['username', 'password', 'password_type', 'hash_type', 'service', 'notes']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if not update_fields:
        return jsonify({"error": "No fields to update"}), 400

    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(cred_id)

    query = f"UPDATE host_credentials SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch updated credential
    cursor.execute('''
        SELECT id, host_id, username, password, password_type, hash_type, service, notes, created_at, updated_at
        FROM host_credentials WHERE id = ?
    ''', (cred_id,))
    row = cursor.fetchone()

    return jsonify({
        "id": row[0],
        "host_id": row[1],
        "username": row[2],
        "password": None,  # masked; reveal via .../secret (M-9)
        "has_secret": bool(row[3]),
        "password_type": row[4],
        "hash_type": row[5],
        "service": row[6],
        "notes": row[7],
        "created_at": row[8],
        "updated_at": row[9]
    }), 200


@hosts_bp.route('/<int:host_id>/credentials/<int:cred_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_credential(host_id, cred_id):
    """Delete a credential entry."""
    engagement_id, error = require_active_engagement()
    if error:
        return error

    cursor = g.db.cursor()

    # Verify host belongs to engagement
    cursor.execute('''
        SELECT id FROM hosts WHERE id = ? AND engagement_id = ?
    ''', (host_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "Host not found"}), 404

    # Verify credential belongs to host
    cursor.execute('''
        SELECT id FROM host_credentials WHERE id = ? AND host_id = ?
    ''', (cred_id, host_id))
    if not cursor.fetchone():
        return jsonify({"error": "Credential not found"}), 404

    cursor.execute('DELETE FROM host_credentials WHERE id = ?', (cred_id,))
    g.db.commit()

    return '', 204

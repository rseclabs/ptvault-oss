"""Engagement management routes for PTVault."""

from flask import Blueprint, request, jsonify, g, session, Response
from middleware.auth import engagement_role, require_auth, require_engagement_role, require_role
from functools import wraps
from utils.error_handler import handle_errors
import re
import json
from datetime import datetime
from utils.markdown_export import generate_markdown_report
from utils.audit_logger import audit_create, audit_update, audit_delete, audit_export, audit_view
from utils.helpers import normalize_tags


engagements_bp = Blueprint('engagements', __name__, url_prefix='/api/engagements')


def validate_email(email):
    """Basic email validation."""
    if not email:
        return True
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_date(date_str):
    """Validate ISO 8601 date format (YYYY-MM-DD)."""
    if not date_str:
        return True
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_status(status):
    """Validate status value."""
    if not status:
        return True
    return status in ['active', 'completed', 'archived']


def serialize_engagement(row):
    """Convert an engagement database row to a dictionary."""
    d = {
        "id": row[0],
        "name": row[1],
        "client_name": row[2],
        "short_name": row[3],
        "description": row[4],
        "tags": row[5],
        "start_date": row[6],
        "end_date": row[7],
        "status": row[8],
        "contact_name": row[9],
        "contact_email": row[10],
        "contact_phone": row[11],
        "created_at": row[12],
        "updated_at": row[13],
    }
    # team_id column added by migration 016
    try:
        d["team_id"] = row[14]
    except (IndexError, KeyError):
        d["team_id"] = None
    return d


def require_active_engagement(f):
    """
    Decorator to require an active engagement to be set.
    For use in future evidence endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'active_engagement_id') or g.active_engagement_id is None:
            return jsonify({"error": "No active engagement selected"}), 400
        return f(*args, **kwargs)
    return decorated_function


def _resolve_team_assignment(raw_team_id):
    """Validate a requested team_id; returns (team_id, error_response).

    Assigning a team grants its members access, so only an admin or a member
    of that team may assign it. None or '' clears the team.
    """
    if raw_team_id in (None, ''):
        return None, None
    try:
        team_id = int(raw_team_id)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "team_id must be an integer"}), 400)
    if isinstance(raw_team_id, bool):
        return None, (jsonify({"error": "team_id must be an integer"}), 400)

    cursor = g.db.cursor()
    cursor.execute('SELECT id FROM teams WHERE id = ?', (team_id,))
    if not cursor.fetchone():
        return None, (jsonify({"error": "team not found"}), 400)
    if g.current_user_role != 'admin':
        cursor.execute('SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?',
                       (team_id, g.current_user))
        if not cursor.fetchone():
            return None, (jsonify({"error": "you can only assign a team you belong to"}), 403)
    return team_id, None


def get_engagement_export_data(engagement_id, include_secrets=False):
    """
    Credential passwords and hashes are included only when include_secrets
    is True (the caller is an editor or owner); otherwise they are None.

    Helper function to gather complete engagement data for export.
    Returns dictionary with engagement, evidence, hosts, and all related data.
    Raises exception if engagement not found or database error occurs.
    """
    cursor = g.db.cursor()

    # Load engagement
    cursor.execute('SELECT * FROM engagements WHERE id = ?', (engagement_id,))
    engagement_row = cursor.fetchone()

    if not engagement_row:
        raise ValueError('engagement not found')

    engagement = {
        'id': engagement_row[0],
        'name': engagement_row[1],
        'client_name': engagement_row[2],
        'short_name': engagement_row[3],
        'description': engagement_row[4],
        'tags': engagement_row[5],
        'start_date': engagement_row[6],
        'end_date': engagement_row[7],
        'status': engagement_row[8],
        'contact_name': engagement_row[9],
        'contact_email': engagement_row[10],
        'contact_phone': engagement_row[11],
        'created_at': engagement_row[12],
        'updated_at': engagement_row[13]
    }

    # Load all evidence with tags (using JOIN to avoid N+1 queries)
    cursor.execute('''
        SELECT
            e.id, e.engagement_id, e.evidence_type, e.title, e.content,
            e.tags, e.file_path, e.file_name, e.file_size, e.metadata,
            e.created_at, e.updated_at,
            e.tool_name, e.severity_level,
            GROUP_CONCAT(t.name, ',') as tag_names
        FROM evidence e
        LEFT JOIN evidence_tags et ON e.id = et.evidence_id
        LEFT JOIN tags t ON et.tag_id = t.id
        WHERE e.engagement_id = ?
        GROUP BY e.id
        ORDER BY e.created_at DESC
    ''', (engagement_id,))

    evidence_list = []
    for row in cursor.fetchall():
        # Parse tags from junction table
        tag_names = row[14]
        tags = tag_names.split(',') if tag_names else []

        # Parse metadata JSON
        metadata_json = None
        if row[9]:  # metadata field
            try:
                metadata_json = json.loads(row[9])
            except (json.JSONDecodeError, ValueError):
                metadata_json = None

        evidence_dict = {
            'id': row[0],
            'engagement_id': row[1],
            'evidence_type': row[2],
            'title': row[3],
            'content': row[4],
            'tags': tags,
            'file_path': row[6],
            'file_name': row[7],
            'file_size': row[8],
            'metadata': metadata_json,
            'created_at': row[10],
            'updated_at': row[11],
            'tool_name': row[12],
            'severity_level': row[13]
        }
        evidence_list.append(evidence_dict)

    # Load hosts
    cursor.execute('''
        SELECT id, engagement_id, ip, hostname, os, notes, rooted, shell,
               interested, not_interested, out_of_scope, flagged, reviewed,
               created_at, updated_at
        FROM hosts
        WHERE engagement_id = ?
        ORDER BY ip
    ''', (engagement_id,))

    hosts_list = []
    for row in cursor.fetchall():
        hosts_list.append({
            'id': row[0],
            'engagement_id': row[1],
            'ip': row[2],
            'hostname': row[3],
            'os': row[4],
            'notes': row[5],
            'rooted': row[6],
            'has_shell': row[7],
            'interested': row[8],
            'not_interested': row[9],
            'out_of_scope': row[10],
            'flagged': row[11],
            'reviewed': row[12],
            'created_at': row[13],
            'updated_at': row[14]
        })

    # Get all host IDs for this engagement
    host_ids = [h['id'] for h in hosts_list]

    # Load host_notes
    host_notes_list = []
    if host_ids:
        placeholders = ','.join('?' * len(host_ids))
        cursor.execute(f'''
            SELECT id, host_id, content, created_at, updated_at
            FROM host_notes
            WHERE host_id IN ({placeholders})
        ''', host_ids)
        for row in cursor.fetchall():
            host_notes_list.append({
                'id': row[0],
                'host_id': row[1],
                'content': row[2],
                'created_at': row[3],
                'updated_at': row[4]
            })

    # Load host_ports
    host_ports_list = []
    if host_ids:
        cursor.execute(f'''
            SELECT id, host_id, port, protocol, state, service, version, created_at, updated_at
            FROM host_ports
            WHERE host_id IN ({placeholders})
        ''', host_ids)
        for row in cursor.fetchall():
            host_ports_list.append({
                'id': row[0],
                'host_id': row[1],
                'port': row[2],
                'protocol': row[3],
                'state': row[4],
                'service': row[5],
                'version': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            })

    # Load host_credentials
    host_credentials_list = []
    if host_ids:
        cursor.execute(f'''
            SELECT id, host_id, username, password, password_type, hash_type, service, notes, created_at, updated_at
            FROM host_credentials
            WHERE host_id IN ({placeholders})
        ''', host_ids)
        for row in cursor.fetchall():
            host_credentials_list.append({
                'id': row[0],
                'host_id': row[1],
                'username': row[2],
                'password': row[3] if include_secrets else None,
                'has_secret': bool(row[3]),
                'password_type': row[4],
                'hash_type': row[5],
                'service': row[6],
                'notes': row[7],
                'created_at': row[8],
                'updated_at': row[9]
            })

    # Load evidence_hosts junction table
    evidence_hosts_list = []
    if host_ids:
        cursor.execute(f'''
            SELECT evidence_id, host_id, source
            FROM evidence_hosts
            WHERE host_id IN ({placeholders})
        ''', host_ids)
        for row in cursor.fetchall():
            evidence_hosts_list.append({
                'evidence_id': row[0],
                'host_id': row[1],
                'source': row[2]
            })

    # Load engagement_notes
    cursor.execute('''
        SELECT id, engagement_id, content, created_at, updated_at
        FROM engagement_notes
        WHERE engagement_id = ?
    ''', (engagement_id,))

    engagement_notes_list = []
    for row in cursor.fetchall():
        engagement_notes_list.append({
            'id': row[0],
            'engagement_id': row[1],
            'content': row[2],
            'created_at': row[3],
            'updated_at': row[4]
        })

    # Load engagement_credentials
    cursor.execute('''
        SELECT id, engagement_id, username, password_or_hash, credential_type, description, created_at, updated_at
        FROM engagement_credentials
        WHERE engagement_id = ?
    ''', (engagement_id,))

    engagement_credentials_list = []
    for row in cursor.fetchall():
        engagement_credentials_list.append({
            'id': row[0],
            'engagement_id': row[1],
            'username': row[2],
            'password_or_hash': row[3] if include_secrets else None,
            'has_secret': bool(row[3]),
            'credential_type': row[4],
            'description': row[5],
            'created_at': row[6],
            'updated_at': row[7]
        })

    # Load terminal_dumps
    cursor.execute('''
        SELECT id, engagement_id, title, content, session_datetime, created_at, updated_at
        FROM terminal_dumps
        WHERE engagement_id = ?
    ''', (engagement_id,))

    terminal_dumps_list = []
    for row in cursor.fetchall():
        terminal_dumps_list.append({
            'id': row[0],
            'engagement_id': row[1],
            'title': row[2],
            'content': row[3],
            'session_datetime': row[4],
            'created_at': row[5],
            'updated_at': row[6]
        })

    # Load engagement_findings
    cursor.execute('''
        SELECT id, engagement_id, title, ip_address, hostname, criticality, cvss_score,
               finding_content, remediation_content, include_in_report, created_at, updated_at
        FROM engagement_findings
        WHERE engagement_id = ?
    ''', (engagement_id,))

    engagement_findings_list = []
    for row in cursor.fetchall():
        engagement_findings_list.append({
            'id': row[0],
            'engagement_id': row[1],
            'title': row[2],
            'ip_address': row[3],
            'hostname': row[4],
            'criticality': row[5],
            'cvss_score': row[6],
            'finding_content': row[7],
            'remediation_content': row[8],
            'include_in_report': row[9],
            'created_at': row[10],
            'updated_at': row[11]
        })

    # Calculate statistics with aggregation queries

    # Total evidence
    cursor.execute('SELECT COUNT(*) FROM evidence WHERE engagement_id = ?', (engagement_id,))
    total_evidence = cursor.fetchone()[0]

    # Evidence by type
    cursor.execute('''
        SELECT evidence_type, COUNT(*)
        FROM evidence
        WHERE engagement_id = ?
        GROUP BY evidence_type
    ''', (engagement_id,))
    evidence_by_type = {row[0]: row[1] for row in cursor.fetchall()}

    # Evidence by tool (using generated column)
    cursor.execute('''
        SELECT tool_name, COUNT(*)
        FROM evidence
        WHERE engagement_id = ? AND tool_name IS NOT NULL
        GROUP BY tool_name
    ''', (engagement_id,))
    evidence_by_tool = {row[0]: row[1] for row in cursor.fetchall()}

    # Evidence by severity (using generated column)
    cursor.execute('''
        SELECT severity_level, COUNT(*)
        FROM evidence
        WHERE engagement_id = ? AND severity_level IS NOT NULL
        GROUP BY severity_level
    ''', (engagement_id,))
    evidence_by_severity = {row[0]: row[1] for row in cursor.fetchall()}

    # Total unique tags
    cursor.execute('''
        SELECT COUNT(DISTINCT t.id)
        FROM tags t
        JOIN evidence_tags et ON t.id = et.tag_id
        JOIN evidence e ON et.evidence_id = e.id
        WHERE e.engagement_id = ?
    ''', (engagement_id,))
    total_tags = cursor.fetchone()[0]

    # Total files with attachments
    cursor.execute('''
        SELECT COUNT(*)
        FROM evidence
        WHERE engagement_id = ? AND file_path IS NOT NULL
    ''', (engagement_id,))
    total_files = cursor.fetchone()[0]

    statistics = {
        'total_evidence': total_evidence,
        'evidence_by_type': evidence_by_type,
        'evidence_by_tool': evidence_by_tool,
        'evidence_by_severity': evidence_by_severity,
        'total_tags': total_tags,
        'total_files': total_files
    }

    # Build complete export data
    return {
        'engagement': engagement,
        'evidence': evidence_list,
        'hosts': hosts_list,
        'host_notes': host_notes_list,
        'host_ports': host_ports_list,
        'host_credentials': host_credentials_list,
        'evidence_hosts': evidence_hosts_list,
        'engagement_notes': engagement_notes_list,
        'engagement_credentials': engagement_credentials_list,
        'terminal_dumps': terminal_dumps_list,
        'engagement_findings': engagement_findings_list,
        'statistics': statistics,
        'export_metadata': {
            'exported_at': datetime.utcnow().isoformat(),
            'ptvault_version': '1.0.0',
            'format_version': '2.0'
        }
    }


@engagements_bp.route('', methods=['POST'])
@require_auth
@require_role('admin', 'tester')
@handle_errors
def create_engagement():
    """
    Create a new engagement.
    Only 'name' is required, all other fields are optional.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    # Validate required fields
    name = data.get('name')
    if not name:
        return jsonify({"error": "name is required"}), 400

    # Extract optional fields
    client_name = data.get('client_name')
    client_id = data.get('client_id') or None
    short_name = data.get('short_name')
    description = data.get('description')
    tags = normalize_tags(data.get('tags'))
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    status = data.get('status', 'active')
    contact_name = data.get('contact_name')
    contact_email = data.get('contact_email')
    contact_phone = data.get('contact_phone')
    team_id, team_error = _resolve_team_assignment(data.get('team_id'))
    if team_error:
        return team_error

    # Validate status
    if not validate_status(status):
        return jsonify({"error": "status must be 'active', 'completed', or 'archived'"}), 400

    # Validate dates
    if not validate_date(start_date):
        return jsonify({"error": "start_date must be in YYYY-MM-DD format"}), 400
    if not validate_date(end_date):
        return jsonify({"error": "end_date must be in YYYY-MM-DD format"}), 400

    # Validate email
    if contact_email and not validate_email(contact_email):
        return jsonify({"error": "contact_email is invalid"}), 400

    cursor = g.db.cursor()
    cursor.execute(
        """
        INSERT INTO engagements (
            name, client_name, client_id, short_name, description, tags,
            start_date, end_date, status,
            contact_name, contact_email, contact_phone, team_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, client_name, client_id, short_name, description, tags,
         start_date, end_date, status,
         contact_name, contact_email, contact_phone, team_id)
    )
    g.db.commit()
    engagement_id = cursor.lastrowid

    # Add creator as owner (multi-user support)
    if hasattr(g, 'current_user') and g.current_user:
        cursor.execute('''
            INSERT INTO engagement_members (engagement_id, user_id, role, added_by)
            VALUES (?, ?, 'owner', ?)
        ''', (engagement_id, g.current_user, g.current_user))
        g.db.commit()

    audit_create('engagement', engagement_id)

    # Fetch the created engagement
    cursor.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
    row = cursor.fetchone()

    return jsonify(serialize_engagement(row)), 201


@engagements_bp.route('', methods=['GET'])
@require_auth
@handle_errors
def list_engagements():
    """
    List all engagements.
    Optional query param: ?status=active
    """
    status_filter = request.args.get('status')

    # Validate status filter if provided
    if status_filter and not validate_status(status_filter):
        return jsonify({"error": "status must be 'active', 'completed', or 'archived'"}), 400

    cursor = g.db.cursor()

    # Admins see all engagements; others see only those they have access to
    if g.current_user_role == 'admin':
        if status_filter:
            cursor.execute(
                "SELECT * FROM engagements WHERE status = ? ORDER BY created_at DESC",
                (status_filter,)
            )
        else:
            cursor.execute("SELECT * FROM engagements ORDER BY created_at DESC")
    else:
        # Filter: direct engagement_members OR team membership
        where_status = "AND e.status = ?" if status_filter else ""
        params = [g.current_user, g.current_user]
        if status_filter:
            params.append(status_filter)

        cursor.execute(f'''
            SELECT DISTINCT e.* FROM engagements e
            LEFT JOIN engagement_members em ON e.id = em.engagement_id AND em.user_id = ?
            LEFT JOIN team_members tm ON e.team_id = tm.team_id AND tm.user_id = ?
            WHERE (em.user_id IS NOT NULL OR tm.user_id IS NOT NULL)
            {where_status}
            ORDER BY e.created_at DESC
        ''', params)

    rows = cursor.fetchall()
    engagements = [serialize_engagement(row) for row in rows]

    # Enrich with team names
    team_ids = list(set(e['team_id'] for e in engagements if e.get('team_id')))
    team_names = {}
    if team_ids:
        placeholders = ','.join('?' * len(team_ids))
        cursor.execute(f'SELECT id, name FROM teams WHERE id IN ({placeholders})', team_ids)
        team_names = {r[0]: r[1] for r in cursor.fetchall()}

    for eng in engagements:
        eng['team_name'] = team_names.get(eng.get('team_id')) if eng.get('team_id') else None

    return jsonify(engagements), 200


@engagements_bp.route('/<int:engagement_id>', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def get_engagement(engagement_id):
    """Get a single engagement by ID."""
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "engagement not found"}), 404

    return jsonify(serialize_engagement(row)), 200


@engagements_bp.route('/<int:engagement_id>', methods=['PUT'])
@require_auth
@require_engagement_role('owner')
@handle_errors
def update_engagement(engagement_id):
    """Update an engagement. Only updates provided fields."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    # Validate optional fields if provided
    status = data.get('status')
    if status and not validate_status(status):
        return jsonify({"error": "status must be 'active', 'completed', or 'archived'"}), 400

    start_date = data.get('start_date')
    if start_date and not validate_date(start_date):
        return jsonify({"error": "start_date must be in YYYY-MM-DD format"}), 400

    end_date = data.get('end_date')
    if end_date and not validate_date(end_date):
        return jsonify({"error": "end_date must be in YYYY-MM-DD format"}), 400

    contact_email = data.get('contact_email')
    if contact_email and not validate_email(contact_email):
        return jsonify({"error": "contact_email is invalid"}), 400

    # Normalize tags if provided
    tags = data.get('tags')
    if tags is not None:
        tags = normalize_tags(tags)

    if 'team_id' in data:
        current = g.db.execute('SELECT team_id FROM engagements WHERE id = ?', (engagement_id,)).fetchone()
        unchanged = current is not None and data['team_id'] not in (None, '') and str(current[0]) == str(data['team_id'])
        if not unchanged:  # keeping the current team grants nothing new
            data['team_id'], team_error = _resolve_team_assignment(data['team_id'])
            if team_error:
                return team_error

    cursor = g.db.cursor()

    # Check if engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    # Build dynamic UPDATE query
    update_fields = []
    update_values = []

    for field in ['name', 'client_name', 'client_id', 'short_name', 'description',
                  'start_date', 'end_date', 'status',
                  'contact_name', 'contact_email', 'contact_phone', 'team_id']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if tags is not None and 'tags' in data:
        update_fields.append("tags = ?")
        update_values.append(tags)

    if not update_fields:
        return jsonify({"error": "no fields to update"}), 400

    # Always update updated_at
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(engagement_id)

    query = f"UPDATE engagements SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch updated engagement
    cursor.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
    row = cursor.fetchone()

    return jsonify(serialize_engagement(row)), 200


@engagements_bp.route('/<int:engagement_id>', methods=['DELETE'])
@require_auth
@require_role('admin')
@handle_errors
def delete_engagement(engagement_id):
    """
    Delete an engagement and ALL associated data.
    This includes: hosts, evidence, notes, ports, credentials.
    """
    cursor = g.db.cursor()

    # Check if engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    # Get all host IDs for this engagement
    cursor.execute("SELECT id FROM hosts WHERE engagement_id = ?", (engagement_id,))
    host_ids = [row[0] for row in cursor.fetchall()]

    # Delete host-related data for each host
    for host_id in host_ids:
        cursor.execute("DELETE FROM host_notes WHERE host_id = ?", (host_id,))
        cursor.execute("DELETE FROM host_ports WHERE host_id = ?", (host_id,))
        cursor.execute("DELETE FROM host_credentials WHERE host_id = ?", (host_id,))
        cursor.execute("DELETE FROM evidence_hosts WHERE host_id = ?", (host_id,))

    # Delete all hosts for this engagement
    cursor.execute("DELETE FROM hosts WHERE engagement_id = ?", (engagement_id,))

    # Delete all evidence for this engagement
    cursor.execute("DELETE FROM evidence WHERE engagement_id = ?", (engagement_id,))

    # Delete engagement notes
    cursor.execute("DELETE FROM engagement_notes WHERE engagement_id = ?", (engagement_id,))

    # Delete engagement credentials
    cursor.execute("DELETE FROM engagement_credentials WHERE engagement_id = ?", (engagement_id,))

    # Delete terminal dumps
    cursor.execute("DELETE FROM terminal_dumps WHERE engagement_id = ?", (engagement_id,))

    # Delete engagement findings
    cursor.execute("DELETE FROM engagement_findings WHERE engagement_id = ?", (engagement_id,))

    # Clear active engagement if it's the one being deleted
    if session.get('active_engagement_id') == engagement_id:
        session.pop('active_engagement_id', None)

    # Delete the engagement
    cursor.execute("DELETE FROM engagements WHERE id = ?", (engagement_id,))
    audit_delete('engagement', engagement_id)
    g.db.commit()

    return '', 204


@engagements_bp.route('/active', methods=['POST'])
@require_auth
@handle_errors
def set_active_engagement():
    """Set the active engagement for the current session."""
    data = request.get_json()
    if not data or 'engagement_id' not in data:
        return jsonify({"error": "engagement_id required"}), 400

    engagement_id = data['engagement_id']

    if engagement_role(g.db, g.current_user, g.current_user_role, engagement_id) is None:
        return jsonify({"error": "engagement not found"}), 404

    # Store in session
    session['active_engagement_id'] = engagement_id

    return jsonify({"active_engagement_id": engagement_id}), 200


@engagements_bp.route('/active', methods=['GET'])
@require_auth
@handle_errors
def get_active_engagement():
    """Get the active engagement for the current session."""
    active_engagement_id = session.get('active_engagement_id')

    if not active_engagement_id:
        return jsonify({"active_engagement_id": None}), 200

    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM engagements WHERE id = ?", (active_engagement_id,))
    row = cursor.fetchone()

    if not row:
        # Active engagement was deleted, clear from session
        session.pop('active_engagement_id', None)
        return jsonify({"active_engagement_id": None}), 200

    return jsonify(serialize_engagement(row)), 200


@engagements_bp.route('/active', methods=['DELETE'])
@require_auth
def clear_active_engagement():
    """Clear the active engagement from the current session."""
    session.pop('active_engagement_id', None)
    return '', 204


# ============================================================================
# Engagement Notes Endpoints (for General section notes)
# ============================================================================

def _engagement_note_dao():
    """Build a NoteTreeDAO bound to engagement_notes for a request."""
    from models.dao.note_tree_dao import NoteTreeDAO
    return NoteTreeDAO('engagement_notes', 'engagement_id')


def _verify_engagement_exists(engagement_id):
    cursor = g.db.cursor()
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    return cursor.fetchone() is not None


@engagements_bp.route('/<int:engagement_id>/notes', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def get_engagement_notes(engagement_id):
    """Get all notes for an engagement (flat list for tree-build)."""
    if not _verify_engagement_exists(engagement_id):
        return jsonify({"error": "engagement not found"}), 404
    notes = _engagement_note_dao().list_for(engagement_id)
    return jsonify(notes), 200


@engagements_bp.route('/<int:engagement_id>/notes/<int:note_id>', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def get_engagement_note(engagement_id, note_id):
    """Get full content for a single engagement note (lazy-load companion)."""
    note = _engagement_note_dao().get_full(note_id, engagement_id)
    if not note:
        return jsonify({"error": "note not found"}), 404
    return jsonify(note), 200


@engagements_bp.route('/<int:engagement_id>/notes', methods=['POST'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def create_engagement_note(engagement_id):
    """Create a new note for an engagement.

    Optional body fields:
      parent_id (int|null): nest under another note in the same engagement
      sort_order (int): explicit ordering; defaults to max+1 within parent
    """
    data = request.get_json() or {}
    content = data.get('content', '')
    title = data.get('title', 'New note')

    if not _verify_engagement_exists(engagement_id):
        return jsonify({"error": "engagement not found"}), 404

    parent_id = data.get('parent_id')
    sort_order = data.get('sort_order')

    dao = _engagement_note_dao()
    if not dao.parent_belongs_to_scope(parent_id, engagement_id):
        return jsonify({"error": "parent note not found in this engagement"}), 400

    note_id = dao.create(
        engagement_id, content, title=title,
        parent_id=parent_id, sort_order=sort_order,
    )
    return jsonify(dao.get_full(note_id, engagement_id)), 201


@engagements_bp.route('/<int:engagement_id>/notes/<int:note_id>', methods=['PUT'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def update_engagement_note(engagement_id, note_id):
    """Update an engagement note's content and/or title."""
    data = request.get_json() or {}
    content = data.get('content')
    title = data.get('title')

    if content is None and title is None:
        return jsonify({"error": "content or title is required"}), 400

    dao = _engagement_note_dao()
    note = dao.get_full(note_id, engagement_id)
    if not note:
        return jsonify({"error": "note not found"}), 404

    new_content = content if content is not None else note['content']
    new_title = title if title is not None else note.get('title', '')
    if not dao.update(note_id, engagement_id, new_content, new_title):
        return jsonify({"error": "note not found"}), 404
    return jsonify(dao.get_full(note_id, engagement_id)), 200


@engagements_bp.route('/<int:engagement_id>/notes/<int:note_id>', methods=['DELETE'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def delete_engagement_note(engagement_id, note_id):
    """Delete an engagement note. Blocked when it has children."""
    dao = _engagement_note_dao()

    if not dao.get_full(note_id, engagement_id):
        return jsonify({"error": "note not found"}), 404

    child_count = dao.count_children(note_id, engagement_id)
    if child_count > 0:
        return jsonify({
            "error": (
                f"This note has {child_count} child note(s). "
                "Delete or move them first."
            ),
            "child_count": child_count,
        }), 409

    dao.delete(note_id, engagement_id)
    return '', 204


@engagements_bp.route(
    '/<int:engagement_id>/notes/<int:note_id>/move', methods=['POST']
)
@require_auth
@require_engagement_role('editor')
@handle_errors
def move_engagement_note(engagement_id, note_id):
    """Move/reorder an engagement note within the tree.

    Body: { "parent_id": int|null, "sort_order": int|null }

    Refuses cycles (returns 400 with a descriptive error). Used by
    drag-drop, indent/outdent, and move-up/down on the frontend.
    """
    data = request.get_json() or {}
    parent_id = data.get('parent_id')
    sort_order = data.get('sort_order')

    dao = _engagement_note_dao()
    if not dao.get_full(note_id, engagement_id):
        return jsonify({"error": "note not found"}), 404

    try:
        dao.move(note_id, engagement_id, parent_id, sort_order)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(dao.get_full(note_id, engagement_id)), 200


@engagements_bp.route('/<int:engagement_id>/export/json', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def export_engagement_json(engagement_id):
    """
    Export engagement data to JSON format.
    Returns complete engagement data with evidence, tags, metadata, and statistics.
    """
    try:
        # Get complete engagement data
        export_data = get_engagement_export_data(
            engagement_id, include_secrets=g.engagement_role in ('editor', 'owner'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

    audit_export('engagement', engagement_id, engagement_id=engagement_id, format='json')

    response = jsonify(export_data)
    response.headers['Content-Disposition'] = f'attachment; filename="ptvault-export-{engagement_id}.json"'
    return response


@engagements_bp.route('/<int:engagement_id>/export/markdown', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def export_engagement_markdown(engagement_id):
    """
    Export engagement data to Markdown format.
    Returns a well-formatted Markdown report ready for report writing.
    """
    try:
        # Get complete engagement data
        export_data = get_engagement_export_data(engagement_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

    audit_export('engagement', engagement_id, engagement_id=engagement_id, format='markdown')

    # Generate Markdown report
    markdown_content = generate_markdown_report(export_data)

    response = Response(markdown_content, mimetype='text/markdown')
    response.headers['Content-Disposition'] = f'attachment; filename="report-{engagement_id}.md"'
    return response


def import_engagement_data(data):
    """
    Import engagement data from a JSON export file.
    Creates new engagement with "(Restored)" suffix and imports all related data.
    Returns the new engagement ID.
    """
    cursor = g.db.cursor()

    # Extract engagement data
    eng_data = data.get('engagement', {})

    # Generate unique name with (Restored) suffix
    base_name = eng_data.get('name', 'Imported Engagement')
    new_name = f"{base_name} (Restored)"

    # Check for duplicate names and increment if needed
    cursor.execute("SELECT COUNT(*) FROM engagements WHERE name LIKE ?", (f"{base_name} (Restored%",))
    existing_count = cursor.fetchone()[0]
    if existing_count > 0:
        new_name = f"{base_name} (Restored {existing_count + 1})"

    # Create new engagement
    cursor.execute('''
        INSERT INTO engagements (
            name, client_name, short_name, description, tags,
            start_date, end_date, status,
            contact_name, contact_email, contact_phone
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        new_name,
        eng_data.get('client_name'),
        eng_data.get('short_name'),
        eng_data.get('description'),
        eng_data.get('tags'),
        eng_data.get('start_date'),
        eng_data.get('end_date'),
        eng_data.get('status', 'active'),
        eng_data.get('contact_name'),
        eng_data.get('contact_email'),
        eng_data.get('contact_phone')
    ))
    new_engagement_id = cursor.lastrowid

    # ID mapping dictionaries (old_id -> new_id)
    host_id_map = {}
    evidence_id_map = {}

    # Import hosts first (needed for foreign keys)
    hosts = data.get('hosts', [])
    for host in hosts:
        old_host_id = host.get('id')
        cursor.execute('''
            INSERT INTO hosts (
                engagement_id, ip, hostname, os, notes, rooted, shell,
                interested, not_interested, out_of_scope, flagged, reviewed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_engagement_id,
            host.get('ip'),
            host.get('hostname'),
            host.get('os'),
            host.get('notes'),
            host.get('rooted', 0),
            host.get('has_shell', host.get('shell', 0)),
            host.get('interested', 0),
            host.get('not_interested', 0),
            host.get('out_of_scope', 0),
            host.get('flagged', 0),
            host.get('reviewed', 0)
        ))
        host_id_map[old_host_id] = cursor.lastrowid

    # Import evidence items
    evidence_items = data.get('evidence', [])
    for ev in evidence_items:
        old_evidence_id = ev.get('id')

        # Convert metadata to JSON string if it's a dict
        metadata = ev.get('metadata')
        if metadata and isinstance(metadata, dict):
            metadata = json.dumps(metadata)

        # Convert tags list to comma-separated string for legacy column
        tags = ev.get('tags', [])
        tags_str = ','.join(tags) if tags else None

        cursor.execute('''
            INSERT INTO evidence (
                engagement_id, evidence_type, title, content, tags,
                file_path, file_name, file_size, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_engagement_id,
            ev.get('evidence_type'),
            ev.get('title'),
            ev.get('content'),
            tags_str,
            ev.get('file_path'),
            ev.get('file_name'),
            ev.get('file_size'),
            metadata
        ))
        new_evidence_id = cursor.lastrowid
        evidence_id_map[old_evidence_id] = new_evidence_id

        # Handle tags via evidence_tags junction table
        for tag_name in tags:
            if not tag_name:
                continue
            # Get or create tag
            cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
            tag_row = cursor.fetchone()
            if tag_row:
                tag_id = tag_row[0]
            else:
                cursor.execute('INSERT INTO tags (name) VALUES (?)', (tag_name,))
                tag_id = cursor.lastrowid

            # Link tag to evidence
            cursor.execute('''
                INSERT OR IGNORE INTO evidence_tags (evidence_id, tag_id)
                VALUES (?, ?)
            ''', (new_evidence_id, tag_id))

    # Import host_notes
    host_notes = data.get('host_notes', [])
    for note in host_notes:
        old_host_id = note.get('host_id')
        new_host_id = host_id_map.get(old_host_id)
        if new_host_id:
            cursor.execute('''
                INSERT INTO host_notes (host_id, content)
                VALUES (?, ?)
            ''', (new_host_id, note.get('content')))

    # Import host_ports
    host_ports = data.get('host_ports', [])
    for port in host_ports:
        old_host_id = port.get('host_id')
        new_host_id = host_id_map.get(old_host_id)
        if new_host_id:
            cursor.execute('''
                INSERT INTO host_ports (host_id, port, protocol, state, service, version)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                new_host_id,
                port.get('port'),
                port.get('protocol'),
                port.get('state'),
                port.get('service'),
                port.get('version')
            ))

    # Import host_credentials
    host_credentials = data.get('host_credentials', [])
    for cred in host_credentials:
        old_host_id = cred.get('host_id')
        new_host_id = host_id_map.get(old_host_id)
        if new_host_id:
            cursor.execute('''
                INSERT INTO host_credentials (host_id, username, password, password_type, hash_type, service, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_host_id,
                cred.get('username'),
                cred.get('password'),
                cred.get('password_type'),
                cred.get('hash_type'),
                cred.get('service'),
                cred.get('notes')
            ))

    # Import evidence_hosts junction table
    evidence_hosts = data.get('evidence_hosts', [])
    for eh in evidence_hosts:
        old_evidence_id = eh.get('evidence_id')
        old_host_id = eh.get('host_id')
        new_evidence_id = evidence_id_map.get(old_evidence_id)
        new_host_id = host_id_map.get(old_host_id)
        if new_evidence_id and new_host_id:
            cursor.execute('''
                INSERT OR IGNORE INTO evidence_hosts (evidence_id, host_id, source)
                VALUES (?, ?, ?)
            ''', (new_evidence_id, new_host_id, eh.get('source')))

    # Import engagement_notes
    engagement_notes = data.get('engagement_notes', [])
    for note in engagement_notes:
        cursor.execute('''
            INSERT INTO engagement_notes (engagement_id, content)
            VALUES (?, ?)
        ''', (new_engagement_id, note.get('content')))

    # Import engagement_credentials
    engagement_credentials = data.get('engagement_credentials', [])
    for cred in engagement_credentials:
        cursor.execute('''
            INSERT INTO engagement_credentials (engagement_id, username, password_or_hash, credential_type, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            new_engagement_id,
            cred.get('username'),
            cred.get('password_or_hash'),
            cred.get('credential_type'),
            cred.get('description')
        ))

    # Import terminal_dumps
    terminal_dumps = data.get('terminal_dumps', [])
    for dump in terminal_dumps:
        cursor.execute('''
            INSERT INTO terminal_dumps (engagement_id, title, content, session_datetime)
            VALUES (?, ?, ?, ?)
        ''', (
            new_engagement_id,
            dump.get('title'),
            dump.get('content'),
            dump.get('session_datetime')
        ))

    # Import engagement_findings
    engagement_findings = data.get('engagement_findings', [])
    for finding in engagement_findings:
        cursor.execute('''
            INSERT INTO engagement_findings (
                engagement_id, title, ip_address, hostname, criticality, cvss_score,
                finding_content, remediation_content, include_in_report
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_engagement_id,
            finding.get('title'),
            finding.get('ip_address'),
            finding.get('hostname'),
            finding.get('criticality'),
            finding.get('cvss_score'),
            finding.get('finding_content'),
            finding.get('remediation_content'),
            finding.get('include_in_report', 1)
        ))

    return new_engagement_id


@engagements_bp.route('/import', methods=['POST'])
@require_auth
@require_role('admin', 'tester')
@handle_errors
def import_engagement():
    """
    Import engagement from a JSON export file.
    Creates a new engagement with "(Restored)" suffix and all associated data.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        data = json.load(file)
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON file'}), 400

    # Validate required fields
    if 'engagement' not in data:
        return jsonify({'error': 'Invalid export format: missing engagement data'}), 400

    if 'export_metadata' not in data:
        return jsonify({'error': 'Invalid export format: missing export_metadata'}), 400

    # Import the engagement data
    new_engagement_id = import_engagement_data(data)
    g.db.commit()

    # Get the created engagement info
    cursor = g.db.cursor()
    cursor.execute('SELECT name FROM engagements WHERE id = ?', (new_engagement_id,))
    row = cursor.fetchone()
    new_name = row[0] if row else 'Unknown'

    return jsonify({
        'success': True,
        'engagement_id': new_engagement_id,
        'engagement_name': new_name,
        'message': 'Engagement imported successfully'
    }), 201


# ============================================================================
# Engagement Credentials Endpoints (for General section credentials)
# ============================================================================

@engagements_bp.route('/<int:engagement_id>/credentials', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def get_engagement_credentials(engagement_id):
    """Get all credentials for an engagement."""
    cursor = g.db.cursor()

    # Verify engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    cursor.execute('''
        SELECT id, engagement_id, username, password_or_hash, credential_type,
               description, created_at, updated_at
        FROM engagement_credentials
        WHERE engagement_id = ?
        ORDER BY created_at DESC
    ''', (engagement_id,))

    credentials = []
    for row in cursor.fetchall():
        credentials.append({
            "id": row[0],
            "engagement_id": row[1],
            "username": row[2],
            "password_or_hash": None,  # masked; reveal via .../secret (M-9)
            "has_secret": bool(row[3]),
            "credential_type": row[4],
            "description": row[5],
            "created_at": row[6],
            "updated_at": row[7]
        })

    return jsonify(credentials), 200


@engagements_bp.route('/<int:engagement_id>/credentials/<int:cred_id>/secret', methods=['GET'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def reveal_engagement_credential(engagement_id, cred_id):
    """Return one credential's password or hash. Editors and above; every reveal is audited."""
    row = g.db.execute(
        'SELECT password_or_hash FROM engagement_credentials WHERE id = ? AND engagement_id = ?',
        (cred_id, engagement_id)
    ).fetchone()
    if not row:
        return jsonify({"error": "credential not found"}), 404
    audit_view('engagement_credential', cred_id, engagement_id=engagement_id, field='password_or_hash')
    return jsonify({"secret": row[0]}), 200


@engagements_bp.route('/<int:engagement_id>/credentials', methods=['POST'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def create_engagement_credential(engagement_id):
    """Create a new credential for an engagement."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    username = data.get('username')
    password_or_hash = data.get('password_or_hash')
    credential_type = data.get('credential_type', 'clear_text')
    description = data.get('description')

    # Validate credential_type
    valid_types = ['clear_text', 'ntlm', 'ntlmv2', 'krbtgt', 'md5', 'sha']
    if credential_type not in valid_types:
        return jsonify({"error": f"credential_type must be one of: {', '.join(valid_types)}"}), 400

    cursor = g.db.cursor()

    # Verify engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    cursor.execute('''
        INSERT INTO engagement_credentials (engagement_id, username, password_or_hash, credential_type, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (engagement_id, username, password_or_hash, credential_type, description))
    g.db.commit()

    cred_id = cursor.lastrowid

    # Fetch the created credential
    cursor.execute('''
        SELECT id, engagement_id, username, password_or_hash, credential_type,
               description, created_at, updated_at
        FROM engagement_credentials WHERE id = ?
    ''', (cred_id,))
    row = cursor.fetchone()

    credential = {
        "id": row[0],
        "engagement_id": row[1],
        "username": row[2],
        "password_or_hash": None,  # masked; reveal via .../secret (M-9)
        "has_secret": bool(row[3]),
        "credential_type": row[4],
        "description": row[5],
        "created_at": row[6],
        "updated_at": row[7]
    }

    return jsonify(credential), 201


@engagements_bp.route('/<int:engagement_id>/credentials/<int:cred_id>', methods=['PUT'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def update_engagement_credential(engagement_id, cred_id):
    """Update an engagement credential."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    # Validate credential_type if provided
    credential_type = data.get('credential_type')
    valid_types = ['clear_text', 'ntlm', 'ntlmv2', 'krbtgt', 'md5', 'sha']
    if credential_type and credential_type not in valid_types:
        return jsonify({"error": f"credential_type must be one of: {', '.join(valid_types)}"}), 400

    cursor = g.db.cursor()

    # Verify credential exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM engagement_credentials
        WHERE id = ? AND engagement_id = ?
    ''', (cred_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "credential not found"}), 404

    # Build dynamic UPDATE query
    update_fields = []
    update_values = []

    for field in ['username', 'password_or_hash', 'credential_type', 'description']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if not update_fields:
        return jsonify({"error": "no fields to update"}), 400

    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(cred_id)

    query = f"UPDATE engagement_credentials SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch the updated credential
    cursor.execute('''
        SELECT id, engagement_id, username, password_or_hash, credential_type,
               description, created_at, updated_at
        FROM engagement_credentials WHERE id = ?
    ''', (cred_id,))
    row = cursor.fetchone()

    credential = {
        "id": row[0],
        "engagement_id": row[1],
        "username": row[2],
        "password_or_hash": None,  # masked; reveal via .../secret (M-9)
        "has_secret": bool(row[3]),
        "credential_type": row[4],
        "description": row[5],
        "created_at": row[6],
        "updated_at": row[7]
    }

    return jsonify(credential), 200


@engagements_bp.route('/<int:engagement_id>/credentials/<int:cred_id>', methods=['DELETE'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def delete_engagement_credential(engagement_id, cred_id):
    """Delete an engagement credential."""
    cursor = g.db.cursor()

    # Verify credential exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM engagement_credentials
        WHERE id = ? AND engagement_id = ?
    ''', (cred_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "credential not found"}), 404

    cursor.execute("DELETE FROM engagement_credentials WHERE id = ?", (cred_id,))
    g.db.commit()

    return '', 204


# ============================================================================
# Terminal Dumps Endpoints (for General section terminal dumps)
# ============================================================================

@engagements_bp.route('/<int:engagement_id>/terminal-dumps', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def get_terminal_dumps(engagement_id):
    """Get all terminal dumps for an engagement."""
    cursor = g.db.cursor()

    # Verify engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    # Terminal dumps often hold large pasted command output (full nmap runs,
    # etc.); return a preview and let the UI fetch full content on expand.
    PREVIEW_LIMIT = 500
    cursor.execute('''
        SELECT id, engagement_id, title, content, session_datetime, created_at, updated_at
        FROM terminal_dumps
        WHERE engagement_id = ?
        ORDER BY session_datetime DESC, created_at DESC
    ''', (engagement_id,))

    dumps = []
    for row in cursor.fetchall():
        content = row[3] or ''
        dumps.append({
            "id": row[0],
            "engagement_id": row[1],
            "title": row[2],
            "content_preview": content[:PREVIEW_LIMIT],
            "has_more": len(content) > PREVIEW_LIMIT,
            "content_length": len(content),
            "session_datetime": row[4],
            "created_at": row[5],
            "updated_at": row[6]
        })

    return jsonify(dumps), 200


@engagements_bp.route('/<int:engagement_id>/terminal-dumps/<int:dump_id>', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def get_terminal_dump(engagement_id, dump_id):
    """Get full content for a single terminal dump (lazy-load companion)."""
    cursor = g.db.cursor()
    cursor.execute('''
        SELECT id, engagement_id, title, content, session_datetime, created_at, updated_at
        FROM terminal_dumps
        WHERE id = ? AND engagement_id = ?
    ''', (dump_id, engagement_id))
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "terminal dump not found"}), 404

    return jsonify({
        "id": row[0],
        "engagement_id": row[1],
        "title": row[2],
        "content": row[3],
        "session_datetime": row[4],
        "created_at": row[5],
        "updated_at": row[6]
    }), 200


@engagements_bp.route('/<int:engagement_id>/terminal-dumps', methods=['POST'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def create_terminal_dump(engagement_id):
    """Create a new terminal dump for an engagement."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    title = data.get('title')
    content = data.get('content')
    session_datetime = data.get('session_datetime')

    if not title:
        return jsonify({"error": "title is required"}), 400
    if not content:
        return jsonify({"error": "content is required"}), 400

    cursor = g.db.cursor()

    # Verify engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    cursor.execute('''
        INSERT INTO terminal_dumps (engagement_id, title, content, session_datetime)
        VALUES (?, ?, ?, ?)
    ''', (engagement_id, title, content, session_datetime))
    g.db.commit()

    dump_id = cursor.lastrowid

    # Fetch the created dump
    cursor.execute('''
        SELECT id, engagement_id, title, content, session_datetime, created_at, updated_at
        FROM terminal_dumps WHERE id = ?
    ''', (dump_id,))
    row = cursor.fetchone()

    dump = {
        "id": row[0],
        "engagement_id": row[1],
        "title": row[2],
        "content": row[3],
        "session_datetime": row[4],
        "created_at": row[5],
        "updated_at": row[6]
    }

    return jsonify(dump), 201


@engagements_bp.route('/<int:engagement_id>/terminal-dumps/<int:dump_id>', methods=['PUT'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def update_terminal_dump(engagement_id, dump_id):
    """Update a terminal dump."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    cursor = g.db.cursor()

    # Verify dump exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM terminal_dumps
        WHERE id = ? AND engagement_id = ?
    ''', (dump_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "terminal dump not found"}), 404

    # Build dynamic UPDATE query
    update_fields = []
    update_values = []

    for field in ['title', 'content', 'session_datetime']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if not update_fields:
        return jsonify({"error": "no fields to update"}), 400

    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(dump_id)

    query = f"UPDATE terminal_dumps SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch the updated dump
    cursor.execute('''
        SELECT id, engagement_id, title, content, session_datetime, created_at, updated_at
        FROM terminal_dumps WHERE id = ?
    ''', (dump_id,))
    row = cursor.fetchone()

    dump = {
        "id": row[0],
        "engagement_id": row[1],
        "title": row[2],
        "content": row[3],
        "session_datetime": row[4],
        "created_at": row[5],
        "updated_at": row[6]
    }

    return jsonify(dump), 200


@engagements_bp.route('/<int:engagement_id>/terminal-dumps/<int:dump_id>', methods=['DELETE'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def delete_terminal_dump(engagement_id, dump_id):
    """Delete a terminal dump."""
    cursor = g.db.cursor()

    # Verify dump exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM terminal_dumps
        WHERE id = ? AND engagement_id = ?
    ''', (dump_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "terminal dump not found"}), 404

    cursor.execute("DELETE FROM terminal_dumps WHERE id = ?", (dump_id,))
    g.db.commit()

    return '', 204


# ============================================================================
# Engagement Findings Endpoints (for General section findings)
# ============================================================================

@engagements_bp.route('/<int:engagement_id>/findings', methods=['GET'])
@require_auth
@require_engagement_role('viewer')
@handle_errors
def get_engagement_findings(engagement_id):
    """Get all findings for an engagement."""
    cursor = g.db.cursor()

    # Verify engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    cursor.execute('''
        SELECT id, engagement_id, title, ip_address, hostname, criticality, cvss_score,
               finding_content, remediation_content, include_in_report,
               created_at, updated_at
        FROM engagement_findings
        WHERE engagement_id = ?
        ORDER BY
            CASE criticality
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            cvss_score DESC,
            created_at DESC
    ''', (engagement_id,))

    findings = []
    for row in cursor.fetchall():
        findings.append({
            "id": row[0],
            "engagement_id": row[1],
            "title": row[2],
            "ip_address": row[3],
            "hostname": row[4],
            "criticality": row[5],
            "cvss_score": row[6],
            "finding_content": row[7],
            "remediation_content": row[8],
            "include_in_report": bool(row[9]),
            "created_at": row[10],
            "updated_at": row[11]
        })

    return jsonify(findings), 200


@engagements_bp.route('/<int:engagement_id>/findings', methods=['POST'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def create_engagement_finding(engagement_id):
    """Create a new finding for an engagement."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    title = data.get('title')
    ip_address = data.get('ip_address')
    hostname = data.get('hostname')
    criticality = data.get('criticality', 'medium')
    cvss_score = data.get('cvss_score')
    finding_content = data.get('finding_content')
    remediation_content = data.get('remediation_content')
    include_in_report = data.get('include_in_report', True)

    if not title:
        return jsonify({"error": "title is required"}), 400

    # Validate criticality
    valid_criticalities = ['critical', 'high', 'medium', 'low']
    if criticality not in valid_criticalities:
        return jsonify({"error": f"criticality must be one of: {', '.join(valid_criticalities)}"}), 400

    # Validate CVSS score if provided
    if cvss_score is not None:
        try:
            cvss_score = float(cvss_score)
            if cvss_score < 0 or cvss_score > 10:
                return jsonify({"error": "cvss_score must be between 0 and 10"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "cvss_score must be a number"}), 400

    cursor = g.db.cursor()

    # Verify engagement exists
    cursor.execute("SELECT id FROM engagements WHERE id = ?", (engagement_id,))
    if not cursor.fetchone():
        return jsonify({"error": "engagement not found"}), 404

    cursor.execute('''
        INSERT INTO engagement_findings
        (engagement_id, title, ip_address, hostname, criticality, cvss_score, finding_content, remediation_content, include_in_report)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (engagement_id, title, ip_address, hostname, criticality, cvss_score, finding_content, remediation_content, 1 if include_in_report else 0))
    g.db.commit()

    finding_id = cursor.lastrowid

    # Fetch the created finding
    cursor.execute('''
        SELECT id, engagement_id, title, ip_address, hostname, criticality, cvss_score,
               finding_content, remediation_content, include_in_report,
               created_at, updated_at
        FROM engagement_findings WHERE id = ?
    ''', (finding_id,))
    row = cursor.fetchone()

    finding = {
        "id": row[0],
        "engagement_id": row[1],
        "title": row[2],
        "ip_address": row[3],
        "hostname": row[4],
        "criticality": row[5],
        "cvss_score": row[6],
        "finding_content": row[7],
        "remediation_content": row[8],
        "include_in_report": bool(row[9]),
        "created_at": row[10],
        "updated_at": row[11]
    }

    return jsonify(finding), 201


@engagements_bp.route('/<int:engagement_id>/findings/<int:finding_id>', methods=['PUT'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def update_engagement_finding(engagement_id, finding_id):
    """Update an engagement finding."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    # Validate criticality if provided
    criticality = data.get('criticality')
    valid_criticalities = ['critical', 'high', 'medium', 'low']
    if criticality and criticality not in valid_criticalities:
        return jsonify({"error": f"criticality must be one of: {', '.join(valid_criticalities)}"}), 400

    # Validate CVSS score if provided
    if 'cvss_score' in data and data['cvss_score'] is not None:
        try:
            cvss_score = float(data['cvss_score'])
            if cvss_score < 0 or cvss_score > 10:
                return jsonify({"error": "cvss_score must be between 0 and 10"}), 400
            data['cvss_score'] = cvss_score
        except (TypeError, ValueError):
            return jsonify({"error": "cvss_score must be a number"}), 400

    cursor = g.db.cursor()

    # Verify finding exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM engagement_findings
        WHERE id = ? AND engagement_id = ?
    ''', (finding_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "finding not found"}), 404

    # Build dynamic UPDATE query
    update_fields = []
    update_values = []

    for field in ['title', 'ip_address', 'hostname', 'criticality', 'cvss_score', 'finding_content', 'remediation_content']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if 'include_in_report' in data:
        update_fields.append("include_in_report = ?")
        update_values.append(1 if data['include_in_report'] else 0)

    if not update_fields:
        return jsonify({"error": "no fields to update"}), 400

    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(finding_id)

    query = f"UPDATE engagement_findings SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch the updated finding
    cursor.execute('''
        SELECT id, engagement_id, title, ip_address, hostname, criticality, cvss_score,
               finding_content, remediation_content, include_in_report,
               created_at, updated_at
        FROM engagement_findings WHERE id = ?
    ''', (finding_id,))
    row = cursor.fetchone()

    finding = {
        "id": row[0],
        "engagement_id": row[1],
        "title": row[2],
        "ip_address": row[3],
        "hostname": row[4],
        "criticality": row[5],
        "cvss_score": row[6],
        "finding_content": row[7],
        "remediation_content": row[8],
        "include_in_report": bool(row[9]),
        "created_at": row[10],
        "updated_at": row[11]
    }

    return jsonify(finding), 200


@engagements_bp.route('/<int:engagement_id>/findings/<int:finding_id>', methods=['DELETE'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def delete_engagement_finding(engagement_id, finding_id):
    """Delete an engagement finding."""
    cursor = g.db.cursor()

    # Verify finding exists and belongs to engagement
    cursor.execute('''
        SELECT id FROM engagement_findings
        WHERE id = ? AND engagement_id = ?
    ''', (finding_id, engagement_id))
    if not cursor.fetchone():
        return jsonify({"error": "finding not found"}), 404

    cursor.execute("DELETE FROM engagement_findings WHERE id = ?", (finding_id,))
    g.db.commit()

    return '', 204


@engagements_bp.route('/<int:engagement_id>/findings/<int:finding_id>/toggle-report', methods=['POST'])
@require_auth
@require_engagement_role('editor')
@handle_errors
def toggle_finding_report_inclusion(engagement_id, finding_id):
    """Toggle whether a finding is included in the final report."""
    cursor = g.db.cursor()

    # Verify finding exists and belongs to engagement
    cursor.execute('''
        SELECT id, include_in_report FROM engagement_findings
        WHERE id = ? AND engagement_id = ?
    ''', (finding_id, engagement_id))
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "finding not found"}), 404

    # Toggle the value
    new_value = 0 if row[1] else 1
    cursor.execute('''
        UPDATE engagement_findings
        SET include_in_report = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_value, finding_id))
    g.db.commit()

    return jsonify({"include_in_report": bool(new_value)}), 200

"""Evidence management routes for PTVault."""

import logging

from flask import Blueprint, request, jsonify, g, send_file
from middleware.auth import require_auth
from routes.engagements import require_active_engagement
from utils.file_helpers import sanitize_filename, allowed_file, create_safe_filepath
from utils.parsers import nmap_parser, burp_parser, nessus_parser
from utils.host_extractor import extract_and_link_hosts_for_evidence, extract_hosts_only
from utils.error_handler import (
    handle_errors,
    ValidationError,
    FileUploadError,
    ParsingError,
    DatabaseError,
    require_fields,
    validate_enum
)
from utils.audit_logger import audit_create, audit_delete
from utils.helpers import normalize_tags
from config import Config
import os
import json
import defusedxml.ElementTree as safe_ET

logger = logging.getLogger(__name__)

evidence_bp = Blueprint('evidence', __name__, url_prefix='/api/evidence')


# Valid evidence types
VALID_EVIDENCE_TYPES = ['note', 'command_output', 'screenshot', 'tool_output', 'other']


def validate_evidence_type(evidence_type):
    """Validate evidence type value."""
    if not evidence_type:
        return False
    return evidence_type in VALID_EVIDENCE_TYPES


def row_to_dict(row):
    """Convert database row to evidence dictionary."""
    return {
        "id": row[0],
        "engagement_id": row[1],
        "evidence_type": row[2],
        "title": row[3],
        "content": row[4],
        "tags": row[5],
        "file_path": row[6],
        "file_name": row[7],
        "file_size": row[8],
        "metadata": row[9],
        "created_at": row[10],
        "updated_at": row[11]
    }


def detect_tool_type(file_path):
    """
    Detect tool type from XML root element.

    Args:
        file_path: Path to the file to detect

    Returns:
        str: Tool type ('nmap', 'burp', 'nessus') or None if unknown
    """
    try:
        tree = safe_ET.parse(file_path)
        root = tree.getroot()

        if root.tag == 'nmaprun':
            return 'nmap'
        elif root.tag == 'issues':
            return 'burp'
        elif root.tag == 'NessusClientData_v2':
            return 'nessus'
        else:
            return None
    except Exception:
        return None


def parse_tool_output(file_path, tool_type):
    """
    Parse tool output file based on detected type.

    Args:
        file_path: Path to the file to parse
        tool_type: Type of tool ('nmap', 'burp', 'nessus')

    Returns:
        dict: Parsed metadata or None if parsing fails

    Raises:
        ParsingError: If parsing fails
    """
    parsers = {
        'nmap': nmap_parser.NmapToolParser(),
        'burp': burp_parser.BurpToolParser(),
        'nessus': nessus_parser.NessusToolParser()
    }

    parser = parsers.get(tool_type)
    if not parser:
        raise ParsingError(f"No parser available for tool type: {tool_type}", tool_type=tool_type)

    try:
        return parser.parse(file_path)
    except ParsingError:
        raise
    except Exception as e:
        raise ParsingError(
            f"Failed to parse {tool_type} output",
            tool_type=tool_type,
            details={'original_error': str(e)}
        )


def auto_generate_tags(metadata):
    """
    Generate tags from parsed metadata.

    Args:
        metadata: Parsed metadata dictionary

    Returns:
        str: Comma-separated tags
    """
    tags = [metadata.get('tool', 'unknown')]

    # Add severity-based tags for Burp/Nessus
    if 'summary' in metadata and 'by_severity' in metadata['summary']:
        severities = metadata['summary']['by_severity']
        if severities.get('Critical', 0) > 0 or severities.get('High', 0) > 0:
            tags.append('critical-findings')

    # Add scan type for nmap
    if metadata.get('tool') == 'nmap' and 'scan_type' in metadata:
        tags.append('port-scan')

    return ','.join(tags)


@evidence_bp.route('', methods=['POST'])
@require_auth
@require_active_engagement
@handle_errors
def create_evidence():
    """
    Create new evidence item with optional file upload.
    Accepts multipart/form-data or JSON.
    """
    # Handle multipart/form-data (with file upload)
    if request.content_type and 'multipart/form-data' in request.content_type:
        title = request.form.get('title')
        evidence_type = request.form.get('evidence_type')
        content = request.form.get('content')
        tags = request.form.get('tags')
        metadata = request.form.get('metadata')
        uploaded_file = request.files.get('file')
    else:
        # Handle JSON
        data = request.get_json()
        if not data:
            raise ValidationError("Request body required")

        title = data.get('title')
        evidence_type = data.get('evidence_type')
        content = data.get('content')
        tags = data.get('tags')
        metadata = data.get('metadata')
        uploaded_file = None

    # Validate required fields
    if not title:
        raise ValidationError("Title is required", field='title')
    if not evidence_type:
        raise ValidationError("Evidence type is required", field='evidence_type')

    # Validate evidence type
    validate_enum(evidence_type, VALID_EVIDENCE_TYPES, 'evidence_type')

    # Normalize tags
    tags = normalize_tags(tags)

    # Validate metadata is valid JSON if provided
    if metadata:
        try:
            json.loads(metadata) if isinstance(metadata, str) else json.dumps(metadata)
        except json.JSONDecodeError:
            raise ValidationError("Metadata must be valid JSON", field='metadata')

    cursor = g.db.cursor()

    # Insert evidence record (without file info initially)
    cursor.execute(
        """
        INSERT INTO evidence (
            engagement_id, evidence_type, title, content, tags, metadata
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (g.active_engagement_id, evidence_type, title, content, tags, metadata)
    )
    g.db.commit()
    evidence_id = cursor.lastrowid

    # Handle file upload if present
    file_path = None
    file_name = None
    file_size = None

    if uploaded_file and uploaded_file.filename:
        # Validate file extension
        if not allowed_file(uploaded_file.filename, Config.ALLOWED_EXTENSIONS):
            # Delete the evidence record we just created
            cursor.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
            g.db.commit()
            return jsonify({"error": f"file type not allowed. Allowed extensions: {', '.join(Config.ALLOWED_EXTENSIONS)}"}), 400

        # Create upload directory if doesn't exist
        engagement_upload_dir = os.path.join(Config.UPLOAD_FOLDER, str(g.active_engagement_id))
        os.makedirs(engagement_upload_dir, exist_ok=True)

        # Generate safe file path
        relative_path, _ = create_safe_filepath(
            g.active_engagement_id,
            evidence_id,
            uploaded_file.filename
        )
        full_path = os.path.join(Config.UPLOAD_FOLDER, relative_path)

        # Check file size
        uploaded_file.seek(0, os.SEEK_END)
        file_size = uploaded_file.tell()
        uploaded_file.seek(0)  # Reset to beginning

        if file_size > Config.MAX_FILE_SIZE:
            # Delete the evidence record
            cursor.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
            g.db.commit()
            return jsonify({"error": f"file size exceeds maximum of {Config.MAX_FILE_SIZE / (1024*1024):.0f} MB"}), 400

        # Save file
        uploaded_file.save(full_path)

        # Update evidence record with file info
        file_path = relative_path
        file_name = uploaded_file.filename

        # Attempt auto-parsing if file is .xml or .nessus
        parsed_metadata = None
        auto_tags = None
        file_ext = os.path.splitext(uploaded_file.filename)[1].lower()

        if file_ext in ['.xml', '.nessus']:
            # Detect tool type
            tool_type = detect_tool_type(full_path)
            logger.debug("File ext: %s, Detected tool: %s", file_ext, tool_type)
            if tool_type:
                # Parse the file
                parsed_metadata = parse_tool_output(full_path, tool_type)
                logger.debug("Parsed metadata: %s", parsed_metadata is not None)
                if parsed_metadata:
                    logger.debug("Tool: %s, Hosts: %d", parsed_metadata.get('tool'), len(parsed_metadata.get('hosts', [])))
                    # Auto-generate tags
                    auto_tags = auto_generate_tags(parsed_metadata)
                    # Merge with existing tags if any
                    if tags:
                        tags = f"{tags},{auto_tags}"
                    else:
                        tags = auto_tags

        cursor.execute(
            """
            UPDATE evidence
            SET file_path = ?, file_name = ?, file_size = ?, metadata = ?, tags = ?
            WHERE id = ?
            """,
            (file_path, file_name, file_size,
             json.dumps(parsed_metadata) if parsed_metadata else None,
             tags, evidence_id)
        )
        g.db.commit()

        # Explicit host link from metadata (e.g. pasted screenshot in a Hosts-tab note).
        # Done BEFORE content-based host extraction so a caller-supplied host_id wins.
        explicit_host_id = None
        if metadata:
            try:
                _meta = json.loads(metadata) if isinstance(metadata, str) else metadata
                explicit_host_id = _meta.get('host_id') if isinstance(_meta, dict) else None
            except (json.JSONDecodeError, TypeError):
                explicit_host_id = None

        if explicit_host_id is not None:
            try:
                host_id_int = int(explicit_host_id)
                # Validate the host belongs to the active engagement before linking.
                # SQLite FK enforcement is off in production, so a bogus host_id
                # would otherwise pollute another engagement's host with an
                # orphaned link row.
                cursor.execute(
                    "SELECT 1 FROM hosts WHERE id = ? AND engagement_id = ?",
                    (host_id_int, g.active_engagement_id),
                )
                if cursor.fetchone() is None:
                    logger.warning(
                        "Refusing to link evidence %s to host %s: host not in active engagement %s",
                        evidence_id, host_id_int, g.active_engagement_id,
                    )
                else:
                    cursor.execute(
                        "INSERT OR IGNORE INTO evidence_hosts (evidence_id, host_id, source) VALUES (?, ?, ?)",
                        (evidence_id, host_id_int, 'note_paste'),
                    )
                    g.db.commit()
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to link evidence %s to host %s: %s",
                               evidence_id, explicit_host_id, e)

        # Extract hosts from parsed metadata
        # For tool_output, we DON'T link evidence to hosts (it stays in General)
        # For other types, we link evidence to the discovered hosts
        if parsed_metadata:
            logger.debug("Extracting hosts for evidence %d, engagement %d", evidence_id, g.active_engagement_id)
            if evidence_type == 'tool_output':
                # Tool output stays in General, only create hosts/ports
                host_count = extract_hosts_only(
                    g.active_engagement_id, parsed_metadata, evidence_id, g.db
                )
                logger.debug("Created %d hosts (not linked to evidence)", host_count)
            else:
                # Other evidence types get linked to hosts
                linked = extract_and_link_hosts_for_evidence(
                    evidence_id, g.active_engagement_id, parsed_metadata, g.db
                )
                logger.debug("Linked %d hosts", linked)
            g.db.commit()

    # Fetch the created evidence
    cursor.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
    row = cursor.fetchone()

    evidence = row_to_dict(row)

    audit_create('evidence', evidence_id, engagement_id=g.active_engagement_id)

    return jsonify(evidence), 201


@evidence_bp.route('', methods=['GET'])
@require_auth
@handle_errors
def list_evidence():
    """
    List evidence for an engagement. Defaults to the active engagement,
    but accepts an explicit ?engagement_id=N when callers (e.g. dashboard
    stats) need data from a different engagement without switching the
    active one. Non-admins must be members of the requested engagement.

    Optional filters:
      ?engagement_id=N - target a specific engagement (admin or member)
      ?type=screenshot
      ?tags=critical,urgent
      ?host_id=123 - filter by specific host
      ?no_host=true - get evidence without any host assignment
    """
    type_filter = request.args.get('type')
    tags_filter = request.args.get('tags')
    host_id = request.args.get('host_id')
    no_host = request.args.get('no_host', '').lower() == 'true'
    requested_eid = request.args.get('engagement_id')

    if requested_eid:
        try:
            target_engagement_id = int(requested_eid)
        except ValueError:
            return jsonify({"error": "engagement_id must be an integer"}), 400

        if g.current_user_role != 'admin':
            access_cursor = g.db.cursor()
            access_cursor.execute('''
                SELECT 1 FROM engagement_members
                WHERE engagement_id = ? AND user_id = ?
                UNION
                SELECT 1 FROM team_members tm
                JOIN engagements e ON e.team_id = tm.team_id
                WHERE e.id = ? AND tm.user_id = ?
                LIMIT 1
            ''', (target_engagement_id, g.current_user,
                  target_engagement_id, g.current_user))
            if not access_cursor.fetchone():
                return jsonify({"error": "no access to engagement"}), 403
    else:
        target_engagement_id = getattr(g, 'active_engagement_id', None)
        if target_engagement_id is None:
            return jsonify({"error": "No active engagement selected"}), 400

    # Validate type filter
    if type_filter and not validate_evidence_type(type_filter):
        return jsonify({"error": f"type must be one of: {', '.join(VALID_EVIDENCE_TYPES)}"}), 400

    cursor = g.db.cursor()

    # Build query with filters
    if host_id:
        # Filter by specific host
        query = """
            SELECT e.* FROM evidence e
            JOIN evidence_hosts eh ON e.id = eh.evidence_id
            WHERE e.engagement_id = ? AND eh.host_id = ?
        """
        params = [target_engagement_id, int(host_id)]
    elif no_host:
        # Filter evidence without any host
        query = """
            SELECT e.* FROM evidence e
            WHERE e.engagement_id = ?
            AND NOT EXISTS (
                SELECT 1 FROM evidence_hosts eh WHERE eh.evidence_id = e.id
            )
        """
        params = [target_engagement_id]
    else:
        query = "SELECT * FROM evidence WHERE engagement_id = ?"
        params = [target_engagement_id]

    if type_filter:
        query += " AND evidence_type = ?"
        params.append(type_filter)

    if tags_filter:
        # Match any tag (OR condition)
        tag_list = [tag.strip() for tag in tags_filter.split(',')]
        for tag in tag_list:
            query += " AND (tags LIKE ? OR tags LIKE ? OR tags LIKE ? OR tags = ?)"
            params.extend([f"%,{tag},%", f"{tag},%", f"%,{tag}", tag])

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    evidence_list = [row_to_dict(row) for row in rows]

    return jsonify(evidence_list), 200


@evidence_bp.route('/<int:evidence_id>', methods=['GET'])
@require_auth
@require_active_engagement
@handle_errors
def get_evidence(evidence_id):
    """Get a single evidence item by ID."""
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "evidence not found"}), 404

    # Verify engagement_id matches active engagement (data isolation)
    if row[1] != g.active_engagement_id:
        return jsonify({"error": "forbidden - evidence belongs to different engagement"}), 403

    evidence = row_to_dict(row)

    return jsonify(evidence), 200


@evidence_bp.route('/<int:evidence_id>', methods=['PUT'])
@require_auth
@require_active_engagement
@handle_errors
def update_evidence(evidence_id):
    """
    Update evidence item.
    Only updates provided fields: title, tags, content, metadata
    File cannot be updated via PUT (delete and recreate instead)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "request body required"}), 400

    # Validate metadata if provided
    metadata = data.get('metadata')
    if metadata:
        try:
            json.loads(metadata) if isinstance(metadata, str) else json.dumps(metadata)
        except json.JSONDecodeError:
            return jsonify({"error": "metadata must be valid JSON"}), 400

    # Normalize tags if provided
    tags = data.get('tags')
    if tags is not None:
        tags = normalize_tags(tags)

    cursor = g.db.cursor()

    # Check if evidence exists
    cursor.execute("SELECT engagement_id FROM evidence WHERE id = ?", (evidence_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "evidence not found"}), 404

    # Verify engagement_id matches active engagement (data isolation)
    if row[0] != g.active_engagement_id:
        return jsonify({"error": "forbidden - evidence belongs to different engagement"}), 403

    # Build dynamic UPDATE query
    update_fields = []
    update_values = []

    for field in ['title', 'content']:
        if field in data:
            update_fields.append(f"{field} = ?")
            update_values.append(data[field])

    if tags is not None and 'tags' in data:
        update_fields.append("tags = ?")
        update_values.append(tags)

    if metadata is not None and 'metadata' in data:
        update_fields.append("metadata = ?")
        update_values.append(metadata)

    if not update_fields:
        return jsonify({"error": "no fields to update"}), 400

    # Always update updated_at
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    update_values.append(evidence_id)

    query = f"UPDATE evidence SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, update_values)
    g.db.commit()

    # Fetch updated evidence
    cursor.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
    row = cursor.fetchone()

    evidence = row_to_dict(row)

    return jsonify(evidence), 200


@evidence_bp.route('/<int:evidence_id>', methods=['DELETE'])
@require_auth
@require_active_engagement
@handle_errors
def delete_evidence(evidence_id):
    """
    Delete evidence item.
    Also deletes associated file from disk if present.
    """
    cursor = g.db.cursor()

    # Check if evidence exists and get file info
    cursor.execute("SELECT engagement_id, file_path FROM evidence WHERE id = ?", (evidence_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "evidence not found"}), 404

    engagement_id, file_path = row[0], row[1]

    # Verify engagement_id matches active engagement (data isolation)
    if engagement_id != g.active_engagement_id:
        return jsonify({"error": "forbidden - evidence belongs to different engagement"}), 403

    # Delete file from disk if it exists
    if file_path:
        full_path = os.path.join(Config.UPLOAD_FOLDER, file_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except OSError as e:
                # Log but don't fail the deletion
                logger.warning("Could not delete file %s: %s", full_path, e)

    # Delete evidence record
    cursor.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))
    audit_delete('evidence', evidence_id, engagement_id=g.active_engagement_id)
    g.db.commit()

    return '', 204


@evidence_bp.route('/<int:evidence_id>/download', methods=['GET'])
@require_auth
@require_active_engagement
@handle_errors
def download_evidence(evidence_id):
    """
    Download evidence file.
    Returns file with original filename.
    """
    cursor = g.db.cursor()

    # Get evidence with file info
    cursor.execute(
        "SELECT engagement_id, file_path, file_name FROM evidence WHERE id = ?",
        (evidence_id,)
    )
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "evidence not found"}), 404

    engagement_id, file_path, file_name = row[0], row[1], row[2]

    # Verify engagement_id matches active engagement (data isolation)
    if engagement_id != g.active_engagement_id:
        return jsonify({"error": "forbidden - evidence belongs to different engagement"}), 403

    # Verify file exists
    if not file_path:
        return jsonify({"error": "no file attached to this evidence"}), 400

    upload_root = os.path.realpath(Config.UPLOAD_FOLDER)
    full_path = os.path.realpath(os.path.join(Config.UPLOAD_FOLDER, file_path))
    if not full_path.startswith(upload_root + os.sep):
        return jsonify({"error": "forbidden"}), 403

    if not os.path.exists(full_path):
        return jsonify({"error": "file not found on disk"}), 404

    # Send file with original filename
    return send_file(
        full_path,
        as_attachment=True,
        download_name=file_name or "evidence_file"
    )


@evidence_bp.route('/<int:evidence_id>/file', methods=['GET'])
@require_auth
@require_active_engagement
@handle_errors
def view_evidence_file(evidence_id):
    """
    Serve evidence file inline (for <img src> embedding in notes).
    Same auth + engagement isolation as /download, but no Content-Disposition: attachment.
    """
    cursor = g.db.cursor()
    cursor.execute(
        "SELECT engagement_id, file_path, file_name FROM evidence WHERE id = ?",
        (evidence_id,),
    )
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "evidence not found"}), 404

    engagement_id, file_path, file_name = row[0], row[1], row[2]
    if engagement_id != g.active_engagement_id:
        return jsonify({"error": "forbidden - evidence belongs to different engagement"}), 403
    if not file_path:
        return jsonify({"error": "no file attached to this evidence"}), 400

    upload_root = os.path.realpath(Config.UPLOAD_FOLDER)
    full_path = os.path.realpath(os.path.join(Config.UPLOAD_FOLDER, file_path))
    if not full_path.startswith(upload_root + os.sep):
        return jsonify({"error": "forbidden"}), 403

    if not os.path.exists(full_path):
        return jsonify({"error": "file not found on disk"}), 404

    return send_file(full_path, as_attachment=False, conditional=True)


@evidence_bp.route('/<int:evidence_id>/parse', methods=['POST'])
@require_auth
@require_active_engagement
@handle_errors
def parse_evidence(evidence_id):
    """
    Manually parse evidence file to extract metadata.
    Useful for re-parsing or parsing files that weren't auto-parsed on upload.
    """
    cursor = g.db.cursor()

    # Get evidence with file info
    cursor.execute(
        "SELECT engagement_id, file_path, file_name FROM evidence WHERE id = ?",
        (evidence_id,)
    )
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "evidence not found"}), 404

    engagement_id, file_path, file_name = row[0], row[1], row[2]

    # Verify engagement_id matches active engagement (data isolation)
    if engagement_id != g.active_engagement_id:
        return jsonify({"error": "forbidden - evidence belongs to different engagement"}), 403

    # Verify file exists
    if not file_path:
        return jsonify({"error": "no file attached to this evidence"}), 400

    full_path = os.path.join(Config.UPLOAD_FOLDER, file_path)

    if not os.path.exists(full_path):
        return jsonify({"error": "file not found on disk"}), 404

    # Detect tool type
    tool_type = detect_tool_type(full_path)
    if not tool_type:
        return jsonify({"error": "unable to detect tool type - file may not be a supported tool output"}), 400

    # Parse the file
    parsed_metadata = parse_tool_output(full_path, tool_type)
    if not parsed_metadata:
        return jsonify({"error": f"failed to parse {tool_type} output - file may be malformed"}), 400

    # Auto-generate tags
    auto_tags = auto_generate_tags(parsed_metadata)

    # Update evidence with parsed metadata and tags (append tags)
    cursor.execute(
        "SELECT tags FROM evidence WHERE id = ?",
        (evidence_id,)
    )
    existing_tags = cursor.fetchone()[0]

    # Merge tags
    if existing_tags:
        merged_tags = f"{existing_tags},{auto_tags}"
    else:
        merged_tags = auto_tags

    cursor.execute(
        """
        UPDATE evidence
        SET metadata = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (json.dumps(parsed_metadata), merged_tags, evidence_id)
    )
    g.db.commit()

    # Fetch updated evidence
    cursor.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
    row = cursor.fetchone()

    evidence = row_to_dict(row)

    return jsonify(evidence), 200


@evidence_bp.route('/search', methods=['GET'])
@require_auth
@require_active_engagement
@handle_errors
def search_evidence():
    """
    Full-text search across evidence using FTS4.
    Query param 'q' for search query, 'limit' for max results (default 50, max 500).
    Note: Using FTS4 (not FTS5) due to pysqlcipher3 limitations.
    """
    engagement_id = g.active_engagement_id
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 50)), 500)

    if not query:
        return jsonify({'error': 'Query parameter q required'}), 400

    cursor = g.db.cursor()

    # FTS4 search - results are automatically ranked by relevance
    # Join FTS table with evidence table, filter by engagement
    # Note: FTS4 doesn't have bm25() like FTS5, but results are still relevance-ranked
    cursor.execute('''
        SELECT e.id, e.engagement_id, e.evidence_type, e.title, e.content,
               e.tags, e.file_path, e.file_name, e.file_size, e.metadata,
               e.created_at, e.updated_at
        FROM evidence e
        JOIN evidence_fts fts ON e.id = fts.docid
        WHERE e.engagement_id = ?
          AND fts MATCH ?
        LIMIT ?
    ''', (engagement_id, query, limit))

    rows = cursor.fetchall()

    # Convert rows to dicts
    results = []
    for row in rows:
        result = {
            "id": row[0],
            "engagement_id": row[1],
            "evidence_type": row[2],
            "title": row[3],
            "content": row[4],
            "tags": row[5],
            "file_path": row[6],
            "file_name": row[7],
            "file_size": row[8],
            "metadata": row[9],
            "created_at": row[10],
            "updated_at": row[11]
        }
        results.append(result)

    return jsonify({
        'results': results,
        'count': len(results),
        'query': query
    })


@evidence_bp.route('/filter', methods=['GET'])
@require_auth
@require_active_engagement
@handle_errors
def filter_evidence():
    """
    Advanced filtering endpoint with dynamic query builder.
    Supports: type, date_from, date_to, tags (AND), tags_any (OR), tool, severity, limit, offset.
    """
    engagement_id = g.active_engagement_id

    # Parse parameters
    evidence_type = request.args.get('type')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    tags_and = request.args.get('tags', '').split(',') if request.args.get('tags') else []
    tags_or = request.args.get('tags_any', '').split(',') if request.args.get('tags_any') else []
    tool = request.args.get('tool')
    severity = request.args.get('severity')
    limit = min(int(request.args.get('limit', 50)), 500)
    offset = int(request.args.get('offset', 0))

    # Validate evidence type
    if evidence_type and not validate_evidence_type(evidence_type):
        return jsonify({"error": f"type must be one of: {', '.join(VALID_EVIDENCE_TYPES)}"}), 400

    cursor = g.db.cursor()

    # Dynamic query builder
    base_query = 'SELECT DISTINCT e.*'
    from_clause = ' FROM evidence e'
    where_clauses = ['e.engagement_id = ?']
    params = [engagement_id]
    group_by = ''
    having_clause = ''

    # Type filter
    if evidence_type:
        where_clauses.append('e.evidence_type = ?')
        params.append(evidence_type)

    # Date range filter
    if date_from:
        where_clauses.append('e.created_at >= ?')
        params.append(date_from)
    if date_to:
        where_clauses.append('e.created_at <= ?')
        params.append(date_to)

    # Tool filter (generated column)
    if tool:
        where_clauses.append('e.tool_name = ?')
        params.append(tool)

    # Severity filter (generated column)
    if severity:
        where_clauses.append('e.severity_level = ?')
        params.append(severity)

    # Tag filter AND (all tags must match)
    if tags_and:
        tags_and = [t.strip() for t in tags_and if t.strip()]
        if tags_and:
            from_clause += '''
                JOIN evidence_tags et ON e.id = et.evidence_id
                JOIN tags t ON et.tag_id = t.id
            '''
            placeholders = ','.join('?' * len(tags_and))
            where_clauses.append(f't.name IN ({placeholders})')
            params.extend(tags_and)
            group_by = ' GROUP BY e.id'
            having_clause = f' HAVING COUNT(DISTINCT t.id) = {len(tags_and)}'

    # Tag filter OR (any tag matches) - use simpler approach if no AND tags
    elif tags_or:
        tags_or = [t.strip() for t in tags_or if t.strip()]
        if tags_or:
            from_clause += '''
                JOIN evidence_tags et ON e.id = et.evidence_id
                JOIN tags t ON et.tag_id = t.id
            '''
            placeholders = ','.join('?' * len(tags_or))
            where_clauses.append(f't.name IN ({placeholders})')
            params.extend(tags_or)

    # Build final query
    where_sql = ' WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''
    order_by = ' ORDER BY e.created_at DESC'
    pagination = f' LIMIT ? OFFSET ?'

    query = base_query + from_clause + where_sql + group_by + having_clause + order_by + pagination
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Convert to dicts
    results = []
    for row in rows:
        result = {
            "id": row[0],
            "engagement_id": row[1],
            "evidence_type": row[2],
            "title": row[3],
            "content": row[4],
            "tags": row[5],
            "file_path": row[6],
            "file_name": row[7],
            "file_size": row[8],
            "metadata": row[9],
            "created_at": row[10],
            "updated_at": row[11]
        }
        results.append(result)

    # Get total count (without pagination)
    count_query = f'SELECT COUNT(DISTINCT e.id){from_clause}{where_sql}{group_by}{having_clause}'
    cursor.execute(count_query, params[:-2])  # Exclude limit/offset

    # Handle GROUP BY case - count returns multiple rows
    count_rows = cursor.fetchall()
    if group_by:
        total = len(count_rows)
    else:
        total = count_rows[0][0] if count_rows else 0

    return jsonify({
        'results': results,
        'count': len(results),
        'total': total,
        'offset': offset
    })


@evidence_bp.route('/bulk', methods=['POST'])
@require_auth
@require_active_engagement
@handle_errors
def bulk_evidence_operation():
    """
    Perform bulk operations on multiple evidence items.

    Request body:
    {
        "operation": "tag|delete|export|move_to_host",
        "evidence_ids": [1, 2, 3],
        "params": {
            "tags": "critical,reviewed",  # for 'tag' operation
            "host_id": 5                   # for 'move_to_host' operation
        }
    }

    Returns:
    {
        "success": 3,
        "failed": 0,
        "message": "Tagged 3 items"
    }
    """
    data = request.get_json()
    if not data:
        raise ValidationError("Request body required")

    # Validate required fields
    require_fields(data, ['operation', 'evidence_ids'])

    operation = data['operation']
    evidence_ids = data['evidence_ids']
    params = data.get('params', {})

    # Validate operation type
    valid_operations = ['tag', 'delete', 'export', 'move_to_host']
    validate_enum(operation, valid_operations, 'operation')

    # Validate evidence_ids is a non-empty list
    if not isinstance(evidence_ids, list) or len(evidence_ids) == 0:
        raise ValidationError("evidence_ids must be a non-empty array", field='evidence_ids')

    try:
        cursor = g.db.cursor()

        # Verify all evidence items belong to active engagement
        placeholders = ','.join('?' * len(evidence_ids))
        cursor.execute(
            f"SELECT id FROM evidence WHERE id IN ({placeholders}) AND engagement_id = ?",
            (*evidence_ids, g.active_engagement_id)
        )
        valid_ids = [row[0] for row in cursor.fetchall()]

        if len(valid_ids) == 0:
            raise ValidationError("No valid evidence items found for the active engagement")

        success_count = 0
        failed_count = len(evidence_ids) - len(valid_ids)

        # Perform operation in single transaction
        if operation == 'tag':
            # Append tags to all selected items
            if 'tags' not in params or not params['tags']:
                raise ValidationError("tags parameter required for tag operation", field='params.tags')

            new_tags = normalize_tags(params['tags'])
            if not new_tags:
                raise ValidationError("Invalid tags format", field='params.tags')

            for evidence_id in valid_ids:
                # Get existing tags
                cursor.execute("SELECT tags FROM evidence WHERE id = ?", (evidence_id,))
                row = cursor.fetchone()
                existing_tags = row[0] if row and row[0] else ''

                # Merge tags
                if existing_tags:
                    merged_tags = f"{existing_tags},{new_tags}"
                else:
                    merged_tags = new_tags

                # Update evidence
                cursor.execute(
                    "UPDATE evidence SET tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (merged_tags, evidence_id)
                )
                success_count += 1

            g.db.commit()
            message = f"Tagged {success_count} item{'s' if success_count != 1 else ''}"

        elif operation == 'delete':
            # Delete all selected items and their files
            for evidence_id in valid_ids:
                # Get file path before deleting
                cursor.execute("SELECT file_path FROM evidence WHERE id = ?", (evidence_id,))
                row = cursor.fetchone()
                file_path = row[0] if row else None

                # Delete evidence record
                cursor.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))

                # Delete file from disk if it exists
                if file_path:
                    full_path = os.path.join(Config.UPLOAD_FOLDER, file_path)
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                        except OSError as e:
                            logger.warning("Could not delete file %s: %s", full_path, e)

                success_count += 1

            g.db.commit()
            message = f"Deleted {success_count} item{'s' if success_count != 1 else ''}"

        elif operation == 'export':
            # Export selected items as JSON
            cursor.execute(
                f"SELECT * FROM evidence WHERE id IN ({placeholders})",
                valid_ids
            )
            rows = cursor.fetchall()

            exported_items = [row_to_dict(row) for row in rows]
            success_count = len(exported_items)

            return jsonify({
                "success": success_count,
                "failed": failed_count,
                "message": f"Exported {success_count} item{'s' if success_count != 1 else ''}",
                "data": exported_items
            }), 200

        elif operation == 'move_to_host':
            # Link evidence items to a specific host
            if 'host_id' not in params:
                raise ValidationError("host_id parameter required for move_to_host operation", field='params.host_id')

            host_id = params['host_id']

            # Verify host exists and belongs to active engagement
            cursor.execute(
                "SELECT id FROM hosts WHERE id = ? AND engagement_id = ?",
                (host_id, g.active_engagement_id)
            )
            if not cursor.fetchone():
                raise ValidationError("Invalid host_id or host does not belong to active engagement", field='params.host_id')

            for evidence_id in valid_ids:
                # First, remove any existing host links for this evidence
                cursor.execute("DELETE FROM evidence_hosts WHERE evidence_id = ?", (evidence_id,))

                # Then create new link to the specified host
                cursor.execute(
                    "INSERT INTO evidence_hosts (evidence_id, host_id) VALUES (?, ?)",
                    (evidence_id, host_id)
                )
                success_count += 1

            g.db.commit()
            message = f"Moved {success_count} item{'s' if success_count != 1 else ''} to host"

        return jsonify({
            "success": success_count,
            "failed": failed_count,
            "message": message
        }), 200

    except ValidationError:
        raise
    except Exception as e:
        g.db.rollback()
        raise DatabaseError(f"Bulk operation failed: {str(e)}")

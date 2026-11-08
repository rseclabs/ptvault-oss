"""Reporting routes for PTVault - Writeups Database and Report Generator."""

import json
import html
import logging
import re
import uuid
from html.parser import HTMLParser
from flask import Blueprint, request, jsonify, g, Response
from middleware.auth import engagement_role, require_auth, require_engagement_access, require_role, can_edit_shared
from utils.error_handler import handle_errors, internal_error
from utils.pdf_generator import generate_pdf_from_html, generate_pdf_with_cover, HAS_WEASYPRINT
from utils.security_headers import attachment_disposition, untrusted_response_headers

logger = logging.getLogger(__name__)

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

# A saved report structure is a list of item objects, capped in length (L-12).
MAX_REPORT_ITEMS = 1000


def _structure_error(structure):
    if not isinstance(structure, list) or not all(isinstance(item, dict) for item in structure):
        return 'structure must be a list of objects'
    if len(structure) > MAX_REPORT_ITEMS:
        return f'structure has too many items (limit {MAX_REPORT_ITEMS})'
    return None


reporting_bp = Blueprint('reporting', __name__, url_prefix='/api/reporting')


@reporting_bp.route('/writeups', methods=['GET'])
@require_auth
@handle_errors
def list_writeups():
    """
    List all writeups with optional filters.
    Query params:
        - category: Filter by category
        - criticality: Filter by criticality level
        - search: Search in name, description, remediation, tags
        - tags: Filter by tag (comma-separated)
    """
    cursor = g.db.cursor()

    # Build query with filters
    query = "SELECT * FROM writeups WHERE 1=1"
    params = []

    category = request.args.get('category')
    if category and category != 'all':
        query += " AND category = ?"
        params.append(category)

    criticality = request.args.get('criticality')
    if criticality and criticality != 'all':
        query += " AND criticality = ?"
        params.append(criticality)

    writeup_type = request.args.get('writeup_type')
    if writeup_type and writeup_type != 'all':
        query += " AND writeup_type = ?"
        params.append(writeup_type)

    search = request.args.get('search')
    if search:
        query += " AND (name LIKE ? OR description LIKE ? OR remediation LIKE ? OR tags LIKE ?)"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

    tags = request.args.get('tags')
    if tags:
        # Filter by any of the provided tags
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        if tag_list:
            tag_conditions = []
            for tag in tag_list:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            query += f" AND ({' OR '.join(tag_conditions)})"

    query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Convert to list of dicts
    columns = [desc[0] for desc in cursor.description]
    writeups = [dict(zip(columns, row)) for row in rows]

    return jsonify(writeups), 200


@reporting_bp.route('/writeups/<int:writeup_id>', methods=['GET'])
@require_auth
@handle_errors
def get_writeup(writeup_id):
    """Get a single writeup by ID."""
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM writeups WHERE id = ?", (writeup_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Writeup not found"}), 404

    columns = [desc[0] for desc in cursor.description]
    writeup = dict(zip(columns, row))

    return jsonify(writeup), 200


@reporting_bp.route('/writeups/categories', methods=['GET'])
@require_auth
@handle_errors
def list_categories():
    """List all unique categories with counts."""
    cursor = g.db.cursor()

    # Get categories with counts
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM writeups
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY category ASC
    ''')
    categories = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

    # Get criticality counts
    cursor.execute('''
        SELECT criticality, COUNT(*) as count
        FROM writeups
        GROUP BY criticality
        ORDER BY
            CASE criticality
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END
    ''')
    criticalities = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

    # Total count
    cursor.execute("SELECT COUNT(*) FROM writeups")
    total = cursor.fetchone()[0]

    return jsonify({
        "categories": categories,
        "criticalities": criticalities,
        "total": total
    }), 200


@reporting_bp.route('/writeups', methods=['POST'])
@require_auth
@require_role('admin', 'tester')
@handle_errors
def create_writeup():
    """
    Create a new writeup.
    Required: name, writeup_type
    Optional: category, criticality, cvss_score, description, remediation, tags
    Note: For 'narrative' type, criticality, cvss_score, and remediation are ignored
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = data.get('name')
    if not name:
        return jsonify({"error": "name is required"}), 400

    # Get and validate writeup_type
    writeup_type = data.get('writeup_type', 'finding')
    valid_types = ['finding', 'narrative']
    if writeup_type not in valid_types:
        return jsonify({"error": f"writeup_type must be one of: {', '.join(valid_types)}"}), 400

    category = data.get('category', '')
    description = data.get('description', '')
    tags = data.get('tags', '')

    # Title display settings
    show_title_in_report = 1 if data.get('show_title_in_report', 1) else 0
    report_heading_level = data.get('report_heading_level', 'h3')
    if report_heading_level not in ('h1', 'h2', 'h3', 'h4'):
        report_heading_level = 'h3'

    # For findings, get criticality, cvss_score, and remediation
    # For narratives, these fields are null/empty
    if writeup_type == 'finding':
        criticality = data.get('criticality', 'medium')
        cvss_score = data.get('cvss_score')
        remediation = data.get('remediation', '')

        # Validate criticality
        valid_criticalities = ['critical', 'high', 'medium', 'low']
        if criticality not in valid_criticalities:
            return jsonify({"error": f"criticality must be one of: {', '.join(valid_criticalities)}"}), 400

        # Validate CVSS score if provided
        if cvss_score is not None and cvss_score != '':
            try:
                cvss_score = float(cvss_score)
                if cvss_score < 0 or cvss_score > 10:
                    return jsonify({"error": "cvss_score must be between 0 and 10"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "cvss_score must be a valid number"}), 400
        else:
            cvss_score = None
    else:
        # Narrative type - no criticality, cvss, or remediation
        criticality = None
        cvss_score = None
        remediation = None

    cursor = g.db.cursor()
    cursor.execute('''
        INSERT INTO writeups (name, category, criticality, cvss_score, description, remediation, tags, writeup_type, show_title_in_report, report_heading_level, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, category, criticality, cvss_score, description, remediation, tags, writeup_type, show_title_in_report, report_heading_level, g.current_user))

    g.db.commit()
    writeup_id = cursor.lastrowid

    # Return the created writeup
    cursor.execute("SELECT * FROM writeups WHERE id = ?", (writeup_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    new_writeup = dict(zip(columns, row))

    return jsonify(new_writeup), 201


@reporting_bp.route('/writeups/<int:writeup_id>', methods=['PUT'])
@require_auth
@require_role('admin', 'tester')
@handle_errors
def update_writeup(writeup_id):
    """Update a writeup."""
    cursor = g.db.cursor()

    # Check if writeup exists
    cursor.execute("SELECT id, created_by FROM writeups WHERE id = ?", (writeup_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Writeup not found"}), 404
    if not can_edit_shared(row[1]):
        return jsonify({"error": "only the creator or an admin can change this"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Build update query dynamically
    updates = []
    params = []

    if 'name' in data:
        if not data['name']:
            return jsonify({"error": "name cannot be empty"}), 400
        updates.append("name = ?")
        params.append(data['name'])

    if 'category' in data:
        updates.append("category = ?")
        params.append(data['category'])

    if 'criticality' in data:
        valid_criticalities = ['critical', 'high', 'medium', 'low']
        if data['criticality'] not in valid_criticalities:
            return jsonify({"error": f"criticality must be one of: {', '.join(valid_criticalities)}"}), 400
        updates.append("criticality = ?")
        params.append(data['criticality'])

    if 'cvss_score' in data:
        cvss_score = data['cvss_score']
        if cvss_score is not None:
            try:
                cvss_score = float(cvss_score)
                if cvss_score < 0 or cvss_score > 10:
                    return jsonify({"error": "cvss_score must be between 0 and 10"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "cvss_score must be a valid number"}), 400
        updates.append("cvss_score = ?")
        params.append(cvss_score)

    if 'description' in data:
        updates.append("description = ?")
        params.append(data['description'])

    if 'remediation' in data:
        updates.append("remediation = ?")
        params.append(data['remediation'])

    if 'tags' in data:
        updates.append("tags = ?")
        params.append(data['tags'])

    if 'writeup_type' in data:
        valid_types = ['finding', 'narrative']
        if data['writeup_type'] not in valid_types:
            return jsonify({"error": f"writeup_type must be one of: {', '.join(valid_types)}"}), 400
        updates.append("writeup_type = ?")
        params.append(data['writeup_type'])

        # If changing to narrative, clear finding-specific fields
        if data['writeup_type'] == 'narrative':
            updates.append("criticality = ?")
            params.append(None)
            updates.append("cvss_score = ?")
            params.append(None)
            updates.append("remediation = ?")
            params.append(None)

    if 'show_title_in_report' in data:
        updates.append("show_title_in_report = ?")
        params.append(1 if data['show_title_in_report'] else 0)

    if 'report_heading_level' in data:
        heading = data['report_heading_level']
        if heading in ('h1', 'h2', 'h3', 'h4'):
            updates.append("report_heading_level = ?")
            params.append(heading)

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    # Add updated_at timestamp
    updates.append("updated_at = CURRENT_TIMESTAMP")

    params.append(writeup_id)
    query = f"UPDATE writeups SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    g.db.commit()

    # Return updated writeup
    cursor.execute("SELECT * FROM writeups WHERE id = ?", (writeup_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    updated_writeup = dict(zip(columns, row))

    return jsonify(updated_writeup), 200


@reporting_bp.route('/writeups/<int:writeup_id>', methods=['DELETE'])
@require_auth
@require_role('admin', 'tester')
@handle_errors
def delete_writeup(writeup_id):
    """Delete a writeup."""
    cursor = g.db.cursor()

    # Check if writeup exists
    cursor.execute("SELECT id, created_by FROM writeups WHERE id = ?", (writeup_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Writeup not found"}), 404
    if not can_edit_shared(row[1]):
        return jsonify({"error": "only the creator or an admin can change this"}), 403

    cursor.execute("DELETE FROM writeups WHERE id = ?", (writeup_id,))
    g.db.commit()

    return jsonify({"success": True}), 200


# ============================================
# REPORT GENERATOR ENDPOINTS
# ============================================

def _engagement_from_request(raw_engagement_id):
    """Resolve an engagement id from a query string or body; returns (id, error).

    Falls back to the active engagement. The caller must have at least viewer
    access to it; otherwise 404, so engagement ids cannot be probed.
    """
    if raw_engagement_id in (None, ''):
        engagement_id = g.active_engagement_id
        if not engagement_id:
            return None, (jsonify({"error": "engagement_id is required"}), 400)
    else:
        try:
            engagement_id = int(raw_engagement_id)
        except (TypeError, ValueError):
            return None, (jsonify({"error": "engagement_id must be an integer"}), 400)
    if engagement_role(g.db, g.current_user, g.current_user_role, engagement_id) is None:
        return None, (jsonify({"error": "engagement not found"}), 404)
    return engagement_id, None


def _requested_engagement_mismatch(data):
    """Writes go to the verified active engagement; reject a different id in the body."""
    requested = data.get('engagement_id')
    if requested not in (None, '') and str(requested) != str(g.active_engagement_id):
        return jsonify({"error": "engagement_id must be the active engagement"}), 400
    return None


@reporting_bp.route('/reports', methods=['GET'])
@require_auth
@handle_errors
def list_reports():
    """
    List all reports for an engagement.
    Query params:
        - engagement_id: Required - filter by engagement
    """
    engagement_id, error = _engagement_from_request(request.args.get('engagement_id'))
    if error:
        return error

    cursor = g.db.cursor()
    cursor.execute('''
        SELECT id, engagement_id, name, created_at, updated_at
        FROM reports
        WHERE engagement_id = ?
        ORDER BY updated_at DESC
    ''', (engagement_id,))
    rows = cursor.fetchall()

    columns = [desc[0] for desc in cursor.description]
    reports = [dict(zip(columns, row)) for row in rows]

    return jsonify(reports), 200


@reporting_bp.route('/reports/<int:report_id>', methods=['GET'])
@require_auth
@handle_errors
def get_report(report_id):
    """
    Get a single report by ID with hydrated items.
    Returns the report with source data merged into each item.
    """
    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ? AND engagement_id = ?",
                   (report_id, g.active_engagement_id))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Report not found"}), 404

    columns = [desc[0] for desc in cursor.description]
    report = dict(zip(columns, row))

    # Parse structure JSON
    structure = json.loads(report['structure']) if report['structure'] else []

    # Hydrate each item with source data
    hydrated_items = []
    for item in structure:
        hydrated = hydrate_report_item(cursor, item, report['engagement_id'])
        hydrated_items.append(hydrated)

    report['structure'] = structure
    report['hydrated_items'] = hydrated_items

    return jsonify(report), 200


@reporting_bp.route('/reports', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def create_report():
    """
    Create a new report.
    Required: engagement_id, name
    Optional: structure (defaults to empty array)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    mismatch = _requested_engagement_mismatch(data)
    if mismatch:
        return mismatch
    engagement_id = g.active_engagement_id

    name = data.get('name')
    if not name:
        return jsonify({"error": "name is required"}), 400

    structure = data.get('structure', [])
    error = _structure_error(structure)
    if error:
        return jsonify({"error": error}), 400
    structure_json = json.dumps(structure)

    cursor = g.db.cursor()

    # Check for duplicate name within the same engagement
    cursor.execute('''
        SELECT id FROM reports WHERE engagement_id = ? AND name = ?
    ''', (engagement_id, name))
    if cursor.fetchone():
        return jsonify({"error": "A report with this name already exists"}), 400

    cursor.execute('''
        INSERT INTO reports (engagement_id, name, structure)
        VALUES (?, ?, ?)
    ''', (engagement_id, name, structure_json))

    g.db.commit()
    report_id = cursor.lastrowid

    # Return the created report
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    new_report = dict(zip(columns, row))
    new_report['structure'] = json.loads(new_report['structure'])

    return jsonify(new_report), 201


@reporting_bp.route('/reports/<int:report_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def update_report(report_id):
    """Update a report's name or structure."""
    cursor = g.db.cursor()

    # Check if report exists and belongs to the active engagement
    cursor.execute("SELECT id, engagement_id FROM reports WHERE id = ? AND engagement_id = ?",
                   (report_id, g.active_engagement_id))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Report not found"}), 404

    engagement_id = row[1]

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    updates = []
    params = []

    if 'name' in data:
        if not data['name']:
            return jsonify({"error": "name cannot be empty"}), 400

        # Check for duplicate name within the same engagement (excluding current report)
        cursor.execute('''
            SELECT id FROM reports WHERE engagement_id = ? AND name = ? AND id != ?
        ''', (engagement_id, data['name'], report_id))
        if cursor.fetchone():
            return jsonify({"error": "A report with this name already exists"}), 400

        updates.append("name = ?")
        params.append(data['name'])

    if 'structure' in data:
        error = _structure_error(data['structure'])
        if error:
            return jsonify({"error": error}), 400
        structure_json = json.dumps(data['structure'])
        updates.append("structure = ?")
        params.append(structure_json)

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(report_id)

    query = f"UPDATE reports SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    g.db.commit()

    # Return updated report
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    columns = [desc[0] for desc in cursor.description]
    updated_report = dict(zip(columns, row))
    updated_report['structure'] = json.loads(updated_report['structure'])

    return jsonify(updated_report), 200


@reporting_bp.route('/reports/<int:report_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def delete_report(report_id):
    """Delete a report."""
    cursor = g.db.cursor()

    # Check if report exists and belongs to the active engagement
    cursor.execute("SELECT id FROM reports WHERE id = ? AND engagement_id = ?",
                   (report_id, g.active_engagement_id))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Report not found"}), 404

    cursor.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    g.db.commit()

    return jsonify({"success": True}), 200


@reporting_bp.route('/reports/<int:report_id>/export', methods=['GET'])
@require_auth
@handle_errors
def export_report(report_id):
    """
    Export a report in various formats.
    Query params:
        - format: html, markdown, pdf, docx (default: html)
    """
    export_format = request.args.get('format', 'html')
    valid_formats = ['html', 'markdown', 'pdf', 'docx']
    if export_format not in valid_formats:
        return jsonify({"error": f"format must be one of: {', '.join(valid_formats)}"}), 400

    cursor = g.db.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ? AND engagement_id = ?",
                   (report_id, g.active_engagement_id))
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "Report not found"}), 404

    columns = [desc[0] for desc in cursor.description]
    report = dict(zip(columns, row))
    structure = json.loads(report['structure']) if report['structure'] else []

    # Hydrate items
    hydrated_items = []
    for item in structure:
        hydrated = hydrate_report_item(cursor, item, report['engagement_id'])
        hydrated_items.append(hydrated)

    if export_format == 'html':
        html = generate_html_export(report, hydrated_items)
        # Report HTML holds user and scanner content: sandboxed if a browser renders it (M-4)
        return untrusted_response_headers(Response(
            html, mimetype='text/html',
            headers={'Content-Disposition': attachment_disposition(f'{report["name"]}.html', 'report.html')}))

    elif export_format == 'markdown':
        markdown = generate_markdown_export(report, hydrated_items)
        return Response(markdown, mimetype='text/markdown',
                      headers={'Content-Disposition': attachment_disposition(f'{report["name"]}.md', 'report.md')})

    elif export_format == 'pdf':
        if not HAS_WEASYPRINT:
            # Fallback: Return HTML for client-side PDF generation via print
            html_content = generate_html_export(report, hydrated_items, for_print=True)
            return untrusted_response_headers(Response(html_content, mimetype='text/html'))

        try:
            # Get engagement data for cover page
            engagement_id = report.get('engagement_id')
            engagement_data = None

            if engagement_id:
                cursor.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
                eng_row = cursor.fetchone()
                if eng_row:
                    eng_columns = [desc[0] for desc in cursor.description]
                    engagement_data = dict(zip(eng_columns, eng_row))

            # Generate HTML with print-optimized styles
            html_content = generate_html_export(report, hydrated_items, for_print=True)

            # Generate PDF with cover page
            pdf_bytes = generate_pdf_with_cover(
                html_content,
                engagement_data=engagement_data,
                report_name=report['name']
            )

            logger.info(f"Generated PDF for report: {report['name']} ({len(pdf_bytes)} bytes)")

            return Response(pdf_bytes, mimetype='application/pdf',
                          headers={'Content-Disposition': attachment_disposition(f'{report["name"]}.pdf', 'report.pdf')})

        except Exception as e:
            return internal_error(e, 'PDF generation failed')

    elif export_format == 'docx':
        try:
            docx_bytes = generate_docx_export(report, hydrated_items)
            return Response(docx_bytes,
                          mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          headers={'Content-Disposition': attachment_disposition(f'{report["name"]}.docx', 'report.docx')})
        except ImportError:
            return jsonify({"error": "python-docx library not installed. Run: pip install python-docx"}), 500


# ============================================
# HELPER FUNCTIONS
# ============================================

def hydrate_report_item(cursor, item, engagement_id):
    """
    Hydrate a report item with its source data.
    Returns merged data with customizations applied. Engagement findings are
    looked up only within the report's own engagement.
    """
    hydrated = {
        'id': item.get('id'),
        'type': item.get('type'),
        'source_id': item.get('source_id'),
        'position': item.get('position'),
    }

    customizations = item.get('customizations', {})

    # Handle format tools - they don't have database records, return as-is
    if item.get('writeup_type') == 'format_tool' or item.get('type') == 'format_tool':
        hydrated['writeup_type'] = 'format_tool'
        hydrated['format_tool_id'] = item.get('format_tool_id') or item.get('source_id')
        hydrated['toolData'] = item.get('toolData', {})
        hydrated['tableData'] = item.get('tableData')
        hydrated['title'] = item.get('title', '')
        return _normalise_hydrated(hydrated)

    if item['type'] == 'engagement_finding':
        cursor.execute("SELECT * FROM engagement_findings WHERE id = ? AND engagement_id = ?",
                       (item['source_id'], engagement_id))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            source_data = dict(zip(columns, row))

            # Merge with customizations
            hydrated['title'] = customizations.get('title') or source_data.get('title', '')
            hydrated['criticality'] = customizations.get('criticality') or source_data.get('criticality', 'medium')
            hydrated['cvss_score'] = customizations.get('cvss_score') if customizations.get('cvss_score') is not None else source_data.get('cvss_score')
            hydrated['finding_content'] = customizations.get('finding_content') or source_data.get('finding_content', '')
            hydrated['remediation_content'] = customizations.get('remediation_content') or source_data.get('remediation_content', '')
            hydrated['ip_address'] = source_data.get('ip_address')
            hydrated['hostname'] = source_data.get('hostname')
            hydrated['writeup_type'] = 'finding'
        else:
            hydrated['error'] = 'Source finding not found'

    elif item['type'] == 'writeup':
        cursor.execute("SELECT * FROM writeups WHERE id = ?", (item['source_id'],))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            source_data = dict(zip(columns, row))

            # Merge with customizations
            hydrated['title'] = customizations.get('name') or source_data.get('name', '')
            hydrated['criticality'] = customizations.get('criticality') or source_data.get('criticality')
            hydrated['cvss_score'] = customizations.get('cvss_score') if customizations.get('cvss_score') is not None else source_data.get('cvss_score')
            hydrated['finding_content'] = customizations.get('description') or source_data.get('description', '')
            hydrated['remediation_content'] = customizations.get('remediation') or source_data.get('remediation', '')
            hydrated['category'] = source_data.get('category')
            hydrated['writeup_type'] = source_data.get('writeup_type', 'finding')

            # Title display settings: per-report customization overrides writeup defaults
            hydrated['show_title'] = customizations.get('show_title', bool(source_data.get('show_title_in_report', 1)))
            hydrated['heading_level'] = customizations.get('heading_level', source_data.get('report_heading_level', 'h3'))
        else:
            hydrated['error'] = 'Source writeup not found'
            hydrated['show_title'] = customizations.get('show_title', True)
            hydrated['heading_level'] = customizations.get('heading_level', 'h3')

    else:
        # For engagement findings, use customizations or defaults
        hydrated['show_title'] = customizations.get('show_title', True)
        hydrated['heading_level'] = customizations.get('heading_level', 'h3')

    return _normalise_hydrated(hydrated)


# Report items come back from a saved structure any engagement editor can
# write. The id, tool id, criticality and heading level are used in handlers,
# class names and tag names, so only known values are returned (H-10).
_ITEM_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
_FORMAT_TOOL_IDS = frozenset([
    'spacer', 'divider', 'pagebreak', 'sectionheader', 'textblock', 'quote', 'bulletlist', 'numberedlist',
    'checklist', 'codeblock', 'commandoutput', 'alertbox', 'keyfinding', 'evidence', 'imageplaceholder',
    'table', 'twocolumn', 'timeline', 'riskmatrix', 'cvsscard', 'attackmap', 'coloredtable',
])


def _normalise_hydrated(hydrated):
    item_id = hydrated.get('id')
    if not (isinstance(item_id, str) and _ITEM_ID.fullmatch(item_id)):
        hydrated['id'] = str(item_id) if isinstance(item_id, int) and not isinstance(item_id, bool) \
            else str(uuid.uuid4())
    if 'format_tool_id' in hydrated and hydrated['format_tool_id'] not in _FORMAT_TOOL_IDS:
        hydrated['format_tool_id'] = None
    if hydrated.get('criticality') is not None:
        hydrated['criticality'] = _criticality_class(hydrated['criticality'])
    if 'heading_level' in hydrated:
        hydrated['heading_level'] = _heading_tag(hydrated['heading_level'])
    return hydrated


# Tags and attributes allowed in rendered markdown output
_ALLOWED_TAGS = frozenset([
    'p', 'br', 'strong', 'em', 'b', 'i', 'u', 'ul', 'ol', 'li',
    'code', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'h4',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'a', 'hr', 'span', 'div',
])
_ALLOWED_ATTRS = frozenset(['href', 'title', 'class'])
_SAFE_URL_SCHEMES = frozenset(['http', 'https', 'mailto'])


def _safe_href(value):
    """True if a link is relative or uses an allowed scheme (no javascript:, data:, ...)."""
    # Browsers ignore ASCII whitespace and control characters inside a scheme.
    compact = re.sub(r'[\x00-\x20\x7f]', '', value)
    scheme = re.match(r'([A-Za-z][A-Za-z0-9+.-]*):', compact)
    return scheme is None or scheme.group(1).lower() in _SAFE_URL_SCHEMES


class _HTMLSanitizer(HTMLParser):
    """Strip tags not in the allowlist; preserve text and safe attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.result = []

    def handle_starttag(self, tag, attrs):
        if tag in _ALLOWED_TAGS:
            safe_attrs = ' '.join(
                f'{k}="{html.escape(v)}"'
                for k, v in attrs
                if k in _ALLOWED_ATTRS and v is not None and (k != 'href' or _safe_href(v))
            )
            self.result.append(f'<{tag}{" " + safe_attrs if safe_attrs else ""}>')

    def handle_endtag(self, tag):
        if tag in _ALLOWED_TAGS:
            self.result.append(f'</{tag}>')

    def handle_data(self, data):
        self.result.append(html.escape(data, quote=False))

    def handle_entityref(self, name):
        self.result.append(f'&{name};')

    def handle_charref(self, name):
        self.result.append(f'&#{name};')

    def get_output(self):
        return ''.join(self.result)


def _sanitize_html(raw_html):
    """Remove all tags not in the allowlist from an HTML string."""
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(raw_html)
    return sanitizer.get_output()


def render_markdown_content(content):
    """Render markdown content to HTML with sanitization."""
    if not content:
        return ''
    if HAS_MARKDOWN:
        raw = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        return _sanitize_html(raw)
    # Fallback: basic HTML escaping with newlines
    return html.escape(content).replace('\n', '<br>')


# Structural report fields become tag names, class names and CSS, where
# escaping is not enough: accept only known values (H-7).
_HEADING_TAGS = frozenset(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
_CRITICALITIES = frozenset(['critical', 'high', 'medium', 'low', 'info', 'informational'])
_IMAGE_WIDTHS = frozenset(['100%', '75%', '50%', '25%'])


def _as_number(value, default=None, low=None, high=None):
    """A float within [low, high], or default if value is not such a number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or (low is not None and number < low) or (high is not None and number > high):
        return default
    return number


def _heading_tag(value, default='h3'):
    tag = str(value).strip().lower() if value is not None else ''
    return tag if tag in _HEADING_TAGS else default


def _criticality_class(value):
    level = str(value or '').strip().lower()
    return level if level in _CRITICALITIES else 'medium'


def generate_html_export(report, items, for_print=False):
    """Generate HTML export of the report matching the preview exactly."""

    # Comprehensive CSS that matches the preview styling
    css = '''
        /* Base styles */
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px;
            line-height: 1.6;
            color: #1a202c;
            background: #fff;
        }

        /* Report title */
        h1.report-title {
            font-size: 1.75rem;
            margin: 0 0 24px 0;
            padding-bottom: 12px;
            border-bottom: 2px solid #e2e8f0;
            color: #1a202c;
        }

        /* Preview content container */
        .report-preview-content {
            font-size: 0.9rem;
            line-height: 1.6;
        }

        /* Finding styles */
        .preview-finding {
            margin-bottom: 24px;
            padding: 16px;
            border-radius: 8px;
            background: #f5f7fa;
            border-left: 4px solid #718096;
        }

        .preview-finding.criticality-critical { border-left-color: #dc2626; }
        .preview-finding.criticality-high { border-left-color: #ea580c; }
        .preview-finding.criticality-medium { border-left-color: #ca8a04; }
        .preview-finding.criticality-low { border-left-color: #2563eb; }

        .preview-finding h1, .preview-finding h2, .preview-finding h3, .preview-finding h4 {
            margin: 0 0 8px 0;
            color: #1a202c;
        }
        .preview-finding h1 { font-size: 1.75rem; }
        .preview-finding h2 { font-size: 1.5rem; }
        .preview-finding h3 { font-size: 1.2rem; }
        .preview-finding h4 { font-size: 1.05rem; }

        /* Criticality badges */
        .preview-meta {
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
            font-size: 0.8rem;
            align-items: center;
        }

        .criticality-badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
        }

        .criticality-badge.criticality-critical {
            background: rgba(220, 38, 38, 0.15);
            color: #dc2626;
        }
        .criticality-badge.criticality-high {
            background: rgba(234, 88, 12, 0.15);
            color: #ea580c;
        }
        .criticality-badge.criticality-medium {
            background: rgba(202, 138, 4, 0.15);
            color: #b45309;
        }
        .criticality-badge.criticality-low {
            background: rgba(37, 99, 235, 0.15);
            color: #2563eb;
        }

        .cvss {
            color: #4a5568;
            font-weight: 500;
        }

        /* Body content */
        .preview-body {
            margin-bottom: 12px;
            color: #4a5568;
        }

        .preview-body p { margin: 0 0 12px 0; }
        .preview-body ul, .preview-body ol { margin: 0 0 12px 0; padding-left: 24px; }
        .preview-body li { margin-bottom: 4px; }
        .preview-body code {
            background: #e2e8f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Fira Code', Consolas, Monaco, monospace;
            font-size: 0.85em;
        }
        .preview-body pre {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Fira Code', Consolas, Monaco, monospace;
            font-size: 0.85rem;
        }
        .preview-body pre code {
            background: transparent;
            padding: 0;
            color: inherit;
        }

        /* Remediation */
        .preview-remediation {
            background: #f0fdf4;
            padding: 16px;
            border-radius: 8px;
            margin-top: 12px;
        }

        .preview-remediation h4 {
            margin: 0 0 8px 0;
            font-size: 0.9rem;
            color: #15803d;
        }

        .preview-remediation p { margin: 0 0 8px 0; }
        .preview-remediation ul, .preview-remediation ol { margin: 0; padding-left: 24px; }

        /* Narrative styles */
        .preview-narrative {
            margin-bottom: 24px;
            padding: 16px;
            border-radius: 8px;
            background: #eef2ff;
            border-left: 4px solid #4f46e5;
        }

        .preview-narrative h1, .preview-narrative h2, .preview-narrative h3, .preview-narrative h4 {
            margin: 0 0 12px 0;
            color: #1a202c;
        }
        .preview-narrative h1 { font-size: 1.75rem; }
        .preview-narrative h2 { font-size: 1.5rem; }
        .preview-narrative h3 { font-size: 1.2rem; }
        .preview-narrative h4 { font-size: 1.05rem; }

        /* Format tools */
        .preview-spacer { min-height: 2em; }

        .preview-divider {
            border: none;
            border-top: 2px solid #e2e8f0;
            margin: 24px 0;
        }

        .preview-pagebreak {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px 0;
            margin: 16px 0;
            border-top: 2px dashed #e2e8f0;
            border-bottom: 2px dashed #e2e8f0;
            color: #718096;
            font-size: 0.85rem;
            font-style: italic;
        }

        .preview-sectionheader {
            margin: 24px 0 16px 0;
            color: #1a202c;
            border-bottom: 2px solid #4f46e5;
            padding-bottom: 8px;
        }
        h1.preview-sectionheader { font-size: 1.75rem; }
        h2.preview-sectionheader { font-size: 1.5rem; }
        h3.preview-sectionheader { font-size: 1.25rem; border-bottom-width: 1px; }
        h4.preview-sectionheader { font-size: 1.1rem; border-bottom: none; }

        .preview-textblock {
            margin: 16px 0;
            line-height: 1.7;
        }
        .preview-textblock p { margin-bottom: 8px; }

        .preview-quote {
            margin: 24px 0;
            padding: 16px 24px;
            border-left: 4px solid #4f46e5;
            background: #f5f7fa;
            border-radius: 0 8px 8px 0;
            font-style: italic;
        }
        .preview-quote p {
            margin: 0 0 8px 0;
            font-size: 1.1rem;
            line-height: 1.6;
        }
        .preview-quote footer {
            color: #4a5568;
            font-size: 0.9rem;
            font-style: normal;
        }

        .preview-bulletlist, .preview-numberedlist {
            margin: 16px 0;
            padding-left: 24px;
        }
        .preview-bulletlist li, .preview-numberedlist li {
            margin-bottom: 4px;
            line-height: 1.5;
        }

        .preview-checklist {
            margin: 16px 0;
            background: #f5f7fa;
            border-radius: 8px;
            padding: 16px;
        }
        .preview-checklist h4 {
            margin: 0 0 8px 0;
            font-size: 1rem;
            color: #1a202c;
        }
        .preview-checklist ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .preview-checklist li {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 4px 0;
            border-bottom: 1px solid #e2e8f0;
        }
        .preview-checklist li:last-child { border-bottom: none; }
        .preview-checklist li.checked {
            color: #718096;
            text-decoration: line-through;
        }
        .preview-checklist .checkbox { font-size: 1.2rem; }

        .preview-codeblock {
            margin: 16px 0;
            background: #e8ecf1;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: hidden;
        }
        .preview-codeblock .code-title {
            padding: 8px 16px;
            background: #f5f7fa;
            border-bottom: 1px solid #e2e8f0;
            font-size: 0.85rem;
            font-weight: 600;
            color: #4a5568;
        }
        .preview-codeblock pre {
            margin: 0;
            padding: 16px;
            overflow-x: auto;
            font-family: 'Fira Code', Consolas, Monaco, monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            background: #1e1e1e;
            color: #d4d4d4;
        }
        .preview-codeblock code {
            background: transparent;
            padding: 0;
        }

        .preview-commandoutput {
            margin: 16px 0;
            background: #1e1e1e;
            border-radius: 8px;
            overflow: hidden;
            font-family: 'Fira Code', Consolas, Monaco, monospace;
            font-size: 0.85rem;
        }
        .preview-commandoutput .command-line {
            padding: 8px 16px;
            background: #2d2d2d;
            color: #4ec9b0;
            font-weight: 600;
        }
        .preview-commandoutput .command-output {
            padding: 16px;
            color: #d4d4d4;
            white-space: pre-wrap;
            word-break: break-all;
        }

        .preview-alertbox {
            display: flex;
            gap: 16px;
            margin: 16px 0;
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid;
        }
        .preview-alertbox.alert-info {
            background: #eff6ff;
            border-color: #3b82f6;
        }
        .preview-alertbox.alert-warning {
            background: #fffbeb;
            border-color: #f59e0b;
        }
        .preview-alertbox.alert-danger {
            background: #fef2f2;
            border-color: #ef4444;
        }
        .preview-alertbox.alert-success {
            background: #f0fdf4;
            border-color: #10b981;
        }
        .preview-alertbox .alert-icon {
            font-size: 1.5rem;
            flex-shrink: 0;
        }
        .preview-alertbox.alert-info .alert-icon { color: #3b82f6; }
        .preview-alertbox.alert-warning .alert-icon { color: #f59e0b; }
        .preview-alertbox.alert-danger .alert-icon { color: #ef4444; }
        .preview-alertbox.alert-success .alert-icon { color: #10b981; }
        .preview-alertbox .alert-content { flex: 1; }
        .preview-alertbox .alert-title {
            font-weight: 600;
            margin-bottom: 4px;
        }
        .preview-alertbox .alert-body {
            font-size: 0.9rem;
            line-height: 1.5;
        }

        .preview-keyfinding {
            display: flex;
            gap: 16px;
            margin: 16px 0;
            padding: 16px;
            background: linear-gradient(135deg, #eef2ff 0%, #f5f7fa 100%);
            border: 2px solid #4f46e5;
            border-radius: 8px;
        }
        .preview-keyfinding .keyfinding-icon {
            font-size: 1.5rem;
            color: #4f46e5;
            flex-shrink: 0;
        }
        .preview-keyfinding .keyfinding-content { flex: 1; }
        .preview-keyfinding .keyfinding-title {
            font-weight: 700;
            font-size: 1.1rem;
            color: #4f46e5;
            margin-bottom: 4px;
        }
        .preview-keyfinding .keyfinding-body {
            font-size: 0.95rem;
            line-height: 1.5;
        }

        .preview-evidence {
            margin: 16px 0;
            background: #f5f7fa;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: hidden;
        }
        .preview-evidence .evidence-image-placeholder {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 32px;
            background: #e8ecf1;
            color: #718096;
        }
        .preview-evidence .placeholder-icon { font-size: 2rem; margin-bottom: 8px; }
        .preview-evidence .placeholder-text { font-size: 0.9rem; }
        .preview-evidence .evidence-description,
        .preview-evidence .evidence-impact {
            padding: 12px 16px;
            font-size: 0.9rem;
            border-top: 1px solid #e2e8f0;
        }

        .preview-imageplaceholder {
            margin: 16px auto;
            text-align: center;
        }
        .preview-imageplaceholder .placeholder-box {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 48px;
            background: #e8ecf1;
            border: 2px dashed #cbd5e1;
            border-radius: 8px;
            color: #718096;
        }
        .preview-imageplaceholder .placeholder-icon { font-size: 2rem; margin-bottom: 8px; }
        .preview-imageplaceholder .placeholder-text { font-size: 0.9rem; }
        .preview-imageplaceholder .image-caption {
            margin-top: 8px;
            font-size: 0.85rem;
            color: #4a5568;
            font-style: italic;
        }

        .preview-table {
            margin: 16px 0;
            overflow-x: auto;
        }
        .preview-table table {
            width: 100%;
            border-collapse: collapse;
            border: 1px solid #e2e8f0;
            font-size: 0.85rem;
        }
        .preview-table th, .preview-table td {
            padding: 8px 16px;
            border: 1px solid #e2e8f0;
            text-align: left;
        }
        .preview-table th {
            background: #f5f7fa;
            font-weight: 600;
            color: #1a202c;
        }
        .preview-table td {
            background: #fff;
            color: #4a5568;
        }

        .preview-twocolumn {
            display: flex;
            gap: 24px;
            margin: 16px 0;
        }
        .preview-twocolumn .column {
            flex: 1;
            background: #f5f7fa;
            padding: 16px;
            border-radius: 8px;
        }
        .preview-twocolumn .column h4 {
            margin: 0 0 12px 0;
            color: #1a202c;
            font-size: 1rem;
        }
        .preview-twocolumn .column-content {
            font-size: 0.9rem;
            color: #4a5568;
        }

        .preview-timeline {
            margin: 16px 0;
            padding-left: 24px;
            border-left: 2px solid #e2e8f0;
        }
        .preview-timeline .timeline-step {
            position: relative;
            padding-bottom: 24px;
        }
        .preview-timeline .timeline-step:last-child { padding-bottom: 0; }
        .preview-timeline .timeline-marker {
            position: absolute;
            left: -33px;
            width: 20px;
            height: 20px;
            background: #4f46e5;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .preview-timeline .step-number {
            color: white;
            font-size: 0.7rem;
            font-weight: 600;
        }
        .preview-timeline .timeline-content { padding-left: 8px; }
        .preview-timeline .step-time {
            font-size: 0.8rem;
            color: #718096;
            margin-bottom: 2px;
        }
        .preview-timeline .step-title {
            font-weight: 600;
            color: #1a202c;
            margin-bottom: 4px;
        }
        .preview-timeline .step-description {
            font-size: 0.9rem;
            color: #4a5568;
        }

        .preview-riskmatrix {
            margin: 16px 0;
            text-align: center;
        }
        .preview-riskmatrix .matrix-ylabel,
        .preview-riskmatrix .matrix-xlabel {
            font-size: 0.85rem;
            color: #4a5568;
            font-weight: 600;
        }
        .preview-riskmatrix table {
            margin: 8px auto;
            border-collapse: collapse;
        }
        .preview-riskmatrix th, .preview-riskmatrix td {
            padding: 8px 12px;
            border: 1px solid #e2e8f0;
            font-size: 0.8rem;
        }
        .preview-riskmatrix th {
            background: #f5f7fa;
            font-weight: 600;
        }
        .preview-riskmatrix td {
            width: 40px;
            height: 40px;
        }
        .preview-riskmatrix .risk-low { background: #bbf7d0; }
        .preview-riskmatrix .risk-medium { background: #fef08a; }
        .preview-riskmatrix .risk-high { background: #fed7aa; }
        .preview-riskmatrix .risk-critical { background: #fecaca; }
        .preview-riskmatrix .highlighted {
            outline: 3px solid #1a202c;
            outline-offset: -3px;
        }

        .preview-cvsscard {
            display: flex;
            gap: 16px;
            margin: 16px 0;
            padding: 16px;
            background: #f5f7fa;
            border-radius: 8px;
            align-items: flex-start;
        }
        .preview-cvsscard .cvss-score-badge {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 12px 20px;
            border-radius: 8px;
            min-width: 80px;
        }
        .preview-cvsscard .cvss-score-badge.severity-critical { background: #fecaca; color: #991b1b; }
        .preview-cvsscard .cvss-score-badge.severity-high { background: #fed7aa; color: #9a3412; }
        .preview-cvsscard .cvss-score-badge.severity-medium { background: #fef08a; color: #854d0e; }
        .preview-cvsscard .cvss-score-badge.severity-low { background: #bbf7d0; color: #166534; }
        .preview-cvsscard .cvss-score-badge.severity-none { background: #e2e8f0; color: #475569; }
        .preview-cvsscard .score {
            font-size: 1.5rem;
            font-weight: 700;
        }
        .preview-cvsscard .severity {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .preview-cvsscard .cvss-details { flex: 1; }
        .preview-cvsscard .cvss-vector {
            font-family: 'Fira Code', Consolas, Monaco, monospace;
            font-size: 0.8rem;
            color: #4a5568;
            margin-bottom: 8px;
            word-break: break-all;
        }

        /* Print styles */
        @media print {
            body { padding: 20px; max-width: none; }
            .preview-finding, .preview-narrative { break-inside: avoid; }
            .preview-pagebreak { break-after: page; }
        }
    '''

    # Add enhanced print styles when generating for PDF
    if for_print:
        from utils.pdf_generator import get_print_css
        css += get_print_css()

    report_name = html.escape(report["name"])
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_name}</title>
    <style>{css}</style>
</head>
<body>
    <div class="report-preview-content">
'''

    for item in items:
        if item.get('error'):
            continue

        item_type = item.get('type', '')
        writeup_type = item.get('writeup_type', '')

        # Handle format tools
        if writeup_type == 'format_tool' or item_type == 'format_tool':
            tool_id = item.get('format_tool_id') or item.get('source_id', '')
            tool_data = item.get('toolData', {}) or item.get('customizations', {})

            if tool_id == 'spacer':
                html_content += '<div class="preview-spacer"><br><br></div>'
            elif tool_id == 'divider':
                html_content += '<hr class="preview-divider">'
            elif tool_id == 'pagebreak':
                html_content += '<div class="preview-pagebreak"><span>— Page Break —</span></div>'
            elif tool_id == 'sectionheader':
                level = int(_as_number(tool_data.get('level', 2), default=2, low=1, high=6))
                text = html.escape(tool_data.get('text', 'Section Title'))
                number = html.escape(tool_data.get('number', '')) + ' ' if tool_data.get('numbered') and tool_data.get('number') else ''
                html_content += f'<h{level} class="preview-sectionheader">{number}{text}</h{level}>'
            elif tool_id == 'textblock':
                content = tool_data.get('content', '')
                html_content += f'<div class="preview-textblock">{render_markdown_content(content)}</div>'
            elif tool_id == 'quote':
                text = html.escape(tool_data.get('text', ''))
                attribution = tool_data.get('attribution', '')
                footer = f'<footer>— {html.escape(attribution)}</footer>' if attribution else ''
                html_content += f'<blockquote class="preview-quote"><p>{text}</p>{footer}</blockquote>'
            elif tool_id == 'bulletlist':
                items_list = tool_data.get('items', ['Item 1', 'Item 2', 'Item 3'])
                list_items = ''.join(f'<li>{html.escape(str(i))}</li>' for i in items_list)
                html_content += f'<ul class="preview-bulletlist">{list_items}</ul>'
            elif tool_id == 'numberedlist':
                items_list = tool_data.get('items', ['Step 1', 'Step 2', 'Step 3'])
                list_items = ''.join(f'<li>{html.escape(str(i))}</li>' for i in items_list)
                html_content += f'<ol class="preview-numberedlist">{list_items}</ol>'
            elif tool_id == 'checklist':
                title = html.escape(tool_data.get('title', 'Checklist'))
                check_items = tool_data.get('items', [{'text': 'Item 1', 'checked': False}])
                items_html = ''
                for ci in check_items:
                    checked_class = ' checked' if ci.get('checked') else ''
                    checkbox = '☑' if ci.get('checked') else '☐'
                    items_html += f'<li class="{checked_class}"><span class="checkbox">{checkbox}</span><span>{html.escape(str(ci.get("text", "")))}</span></li>'
                html_content += f'<div class="preview-checklist"><h4>{title}</h4><ul>{items_html}</ul></div>'
            elif tool_id == 'codeblock':
                code = html.escape(tool_data.get('code', '# Enter code here'))
                language = html.escape(tool_data.get('language', 'bash'))
                title = tool_data.get('title', '')
                title_html = f'<div class="code-title">{html.escape(title)}</div>' if title else ''
                html_content += f'<div class="preview-codeblock">{title_html}<pre class="language-{language}"><code>{code}</code></pre></div>'
            elif tool_id == 'commandoutput':
                command = html.escape(tool_data.get('command', '$ whoami'))
                output = html.escape(tool_data.get('output', 'root'))
                html_content += f'<div class="preview-commandoutput"><div class="command-line">{command}</div><div class="command-output">{output}</div></div>'
            elif tool_id == 'alertbox':
                alert_type = tool_data.get('type', 'warning')
                title = html.escape(tool_data.get('title', 'Warning'))
                content = html.escape(tool_data.get('content', 'Important information here.'))
                icons = {'info': 'ℹ', 'warning': '⚠', 'danger': '⛔', 'success': '✓'}
                icon = icons.get(alert_type, '⚠')
                html_content += f'<div class="preview-alertbox alert-{html.escape(alert_type)}"><div class="alert-icon">{icon}</div><div class="alert-content"><div class="alert-title">{title}</div><div class="alert-body">{content}</div></div></div>'
            elif tool_id == 'keyfinding':
                title = html.escape(tool_data.get('title', 'Key Finding'))
                content = html.escape(tool_data.get('content', 'Summary of critical discovery.'))
                html_content += f'<div class="preview-keyfinding"><div class="keyfinding-icon">★</div><div class="keyfinding-content"><div class="keyfinding-title">{title}</div><div class="keyfinding-body">{content}</div></div></div>'
            elif tool_id == 'evidence':
                caption = html.escape(tool_data.get('imageCaption', 'Screenshot description'))
                description = html.escape(tool_data.get('description', 'Evidence details...'))
                impact = html.escape(tool_data.get('impact', 'Impact statement...'))
                html_content += f'<div class="preview-evidence"><div class="evidence-image-placeholder"><span class="placeholder-icon">📷</span><span class="placeholder-text">{caption}</span></div><div class="evidence-description"><strong>Description:</strong> {description}</div><div class="evidence-impact"><strong>Impact:</strong> {impact}</div></div>'
            elif tool_id == 'imageplaceholder':
                caption = html.escape(tool_data.get('caption', 'Figure 1: Description'))
                width = tool_data.get('width', '100%')
                width = width if width in _IMAGE_WIDTHS else '100%'
                html_content += f'<div class="preview-imageplaceholder" style="width: {width}"><div class="placeholder-box"><span class="placeholder-icon">🖼</span><span class="placeholder-text">Insert Image Here</span></div><div class="image-caption">{caption}</div></div>'
            elif tool_id == 'table':
                table_data = item.get('tableData') or tool_data.get('tableData', {'headers': ['Column 1', 'Column 2'], 'rows': [['Data 1', 'Data 2']]})
                headers = table_data.get('headers', [])
                rows = table_data.get('rows', [])
                header_html = ''.join(f'<th>{html.escape(str(h))}</th>' for h in headers)
                rows_html = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(c))}</td>' for c in row) + '</tr>' for row in rows)
                html_content += f'<div class="preview-table"><table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table></div>'
            elif tool_id == 'twocolumn':
                left_title = html.escape(tool_data.get('leftTitle', 'Before'))
                left_content = render_markdown_content(tool_data.get('leftContent', 'Left column content...'))
                right_title = html.escape(tool_data.get('rightTitle', 'After'))
                right_content = render_markdown_content(tool_data.get('rightContent', 'Right column content...'))
                html_content += f'<div class="preview-twocolumn"><div class="column"><h4>{left_title}</h4><div class="column-content">{left_content}</div></div><div class="column"><h4>{right_title}</h4><div class="column-content">{right_content}</div></div></div>'
            elif tool_id == 'timeline':
                steps = tool_data.get('steps', [{'time': '10:00', 'title': 'Step 1', 'description': 'Description'}])
                steps_html = ''
                for idx, step in enumerate(steps):
                    steps_html += f'<div class="timeline-step"><div class="timeline-marker"><span class="step-number">{idx + 1}</span></div><div class="timeline-content"><div class="step-time">{html.escape(str(step.get("time", "")))}</div><div class="step-title">{html.escape(str(step.get("title", "")))}</div><div class="step-description">{html.escape(str(step.get("description", "")))}</div></div></div>'
                html_content += f'<div class="preview-timeline">{steps_html}</div>'
            elif tool_id == 'riskmatrix':
                size = 5 if _as_number(tool_data.get('size', 3)) == 5 else 3
                highlighted = tool_data.get('highlighted', {'row': 1, 'col': 2})
                if not isinstance(highlighted, dict):
                    highlighted = {}
                if size == 3:
                    row_labels = ['High', 'Medium', 'Low']
                    col_labels = ['Low', 'Medium', 'High']
                    risk_matrix = [
                        ['high', 'critical', 'critical'],
                        ['medium', 'high', 'critical'],
                        ['low', 'medium', 'high']
                    ]
                else:
                    row_labels = ['Critical', 'High', 'Medium', 'Low', 'Info']
                    col_labels = ['Rare', 'Unlikely', 'Possible', 'Likely', 'Certain']
                    risk_matrix = [
                        ['medium', 'high', 'critical', 'critical', 'critical'],
                        ['low', 'medium', 'high', 'critical', 'critical'],
                        ['low', 'low', 'medium', 'high', 'critical'],
                        ['info', 'low', 'low', 'medium', 'high'],
                        ['info', 'info', 'low', 'low', 'medium']
                    ]
                header_html = '<th></th>' + ''.join(f'<th>{html.escape(c)}</th>' for c in col_labels)
                rows_html = ''
                for row_idx, row_label in enumerate(row_labels):
                    cells_html = f'<th>{html.escape(row_label)}</th>'
                    for col_idx in range(len(col_labels)):
                        risk = risk_matrix[row_idx][col_idx] if row_idx < len(risk_matrix) and col_idx < len(risk_matrix[row_idx]) else 'low'
                        is_highlighted = highlighted.get('row') == row_idx and highlighted.get('col') == col_idx
                        highlight_class = ' highlighted' if is_highlighted else ''
                        cells_html += f'<td class="risk-{risk}{highlight_class}"></td>'
                    rows_html += f'<tr>{cells_html}</tr>'
                html_content += f'<div class="preview-riskmatrix"><div class="matrix-ylabel">Likelihood</div><table class="risk-matrix size-{size}"><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table><div class="matrix-xlabel">Impact</div></div>'
            elif tool_id == 'cvsscard':
                score = _as_number(tool_data.get('score', 7.5), default=0.0, low=0.0, high=10.0)
                vector = html.escape(tool_data.get('vector', 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N'))
                if score >= 9.0:
                    severity = 'Critical'
                elif score >= 7.0:
                    severity = 'High'
                elif score >= 4.0:
                    severity = 'Medium'
                elif score >= 0.1:
                    severity = 'Low'
                else:
                    severity = 'None'
                html_content += f'<div class="preview-cvsscard"><div class="cvss-score-badge severity-{severity.lower()}"><span class="score">{score}</span><span class="severity">{severity}</span></div><div class="cvss-details"><div class="cvss-vector">{vector}</div></div></div>'
            elif tool_id == 'attackmap':
                map_id = tool_data.get('mapId')
                map_name = html.escape(tool_data.get('mapName', 'Attack Map'))
                if map_id:
                    try:
                        from utils.attack_map_svg import generate_attack_map_svg
                        from models.dao.attack_map_dao import AttackMapDAO
                        dao = AttackMapDAO()
                        attack_map = dao.get_full_map(int(map_id))
                        if attack_map:
                            svg_content = generate_attack_map_svg(attack_map)
                            html_content += f'<div class="preview-attackmap"><div style="text-align:center;margin-bottom:8px;font-weight:600;">{map_name}</div>{svg_content}</div>'
                        else:
                            html_content += f'<div class="preview-attackmap"><p>Attack map not found</p></div>'
                    except Exception as svg_err:
                        logger.warning(f"Failed to render attack map SVG: {svg_err}")
                        html_content += f'<div class="preview-attackmap"><p>{map_name} (SVG render failed)</p></div>'
            continue

        # Title display settings
        show_title = item.get('show_title', True)
        heading_level = _heading_tag(item.get('heading_level', 'h3'))

        # Handle narrative
        if writeup_type == 'narrative':
            title = html.escape(item.get('title', 'Untitled'))
            content = render_markdown_content(item.get('finding_content', '') or item.get('description', ''))
            title_html = f'<{heading_level}>{title}</{heading_level}>' if show_title else ''
            html_content += f'''
        <div class="preview-narrative">
            {title_html}
            <div class="preview-body">{content}</div>
        </div>
'''
        # Handle finding
        else:
            title = html.escape(item.get('title', 'Untitled'))
            criticality_label = html.escape(str(item.get('criticality') or 'medium'))
            criticality = _criticality_class(item.get('criticality'))
            cvss = _as_number(item.get('cvss_score'), low=0.0, high=10.0)
            cvss_html = f'<span class="cvss">CVSS: {cvss:g}</span>' if cvss else ''
            content = render_markdown_content(item.get('finding_content', '') or item.get('description', ''))

            remediation_html = ''
            remediation = item.get('remediation_content') or item.get('remediation', '')
            if remediation:
                remediation_content = render_markdown_content(remediation)
                remediation_html = f'<div class="preview-remediation"><h4>Remediation</h4>{remediation_content}</div>'

            title_html = f'<{heading_level}>{title}</{heading_level}>' if show_title else ''
            html_content += f'''
        <div class="preview-finding criticality-{criticality}">
            {title_html}
            <div class="preview-meta">
                <span class="criticality-badge criticality-{criticality}">{criticality_label}</span>
                {cvss_html}
            </div>
            <div class="preview-body">{content}</div>
            {remediation_html}
        </div>
'''

    html_content += '''
    </div>
</body>
</html>'''

    return html_content


def generate_markdown_export(report, items):
    """Generate Markdown export of the report."""
    md = ''

    for item in items:
        if item.get('error'):
            continue

        is_narrative = item.get('writeup_type') == 'narrative'
        show_title = item.get('show_title', True)
        heading_level = item.get('heading_level', 'h3')
        # Map heading level to markdown: h1=#, h2=##, h3=###, h4=####
        md_heading = {'h1': '#', 'h2': '##', 'h3': '###', 'h4': '####'}.get(heading_level, '##')

        if is_narrative:
            if show_title:
                md += f'{md_heading} {item.get("title", "Untitled")}\n\n'
            md += f'{item.get("finding_content", "")}\n\n'
        else:
            criticality = item.get('criticality', 'medium')
            if show_title:
                md += f'{md_heading} {item.get("title", "Untitled")}\n\n'
            md += f'**Criticality:** {criticality.upper()}'
            if item.get('cvss_score'):
                md += f' | **CVSS:** {item.get("cvss_score")}'
            md += '\n\n'
            md += f'{item.get("finding_content", "")}\n\n'
            if item.get('remediation_content'):
                md += f'### Remediation\n\n{item.get("remediation_content")}\n\n'

        md += '---\n\n'

    return md


def generate_docx_export(report, items):
    """Generate DOCX export of the report using python-docx."""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from io import BytesIO

    doc = Document()

    for item in items:
        if item.get('error'):
            continue

        is_narrative = item.get('writeup_type') == 'narrative'
        show_title = item.get('show_title', True)
        heading_level = item.get('heading_level', 'h3')
        # Map heading level to docx heading level: h1=0, h2=1, h3=2, h4=3
        docx_level = {'h1': 0, 'h2': 1, 'h3': 2, 'h4': 3}.get(heading_level, 1)

        # Section heading
        if show_title:
            doc.add_heading(item.get('title', 'Untitled'), docx_level)

        if not is_narrative:
            # Criticality and CVSS
            criticality = item.get('criticality', 'medium')
            meta_para = doc.add_paragraph()
            meta_run = meta_para.add_run(f'Criticality: {criticality.upper()}')
            meta_run.bold = True
            if item.get('cvss_score'):
                meta_para.add_run(f'  |  CVSS: {item.get("cvss_score")}')

        # Content
        if item.get('finding_content'):
            doc.add_paragraph(item.get('finding_content'))

        # Remediation
        if not is_narrative and item.get('remediation_content'):
            doc.add_heading('Remediation', 2)
            doc.add_paragraph(item.get('remediation_content'))

        doc.add_paragraph()  # Spacer

    # Save to bytes
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================
# REPORT TEMPLATES ENDPOINTS
# ============================================

@reporting_bp.route('/templates', methods=['GET'])
@require_auth
@handle_errors
def get_report_templates():
    """Get all available report templates.

    Query params:
        - category: Filter by category (optional)
        - public_only: Return only public templates (optional)
    """
    from models.dao.template_dao import TemplateDAO

    template_dao = TemplateDAO()

    category = request.args.get('category')
    public_only = request.args.get('public_only', 'false').lower() == 'true'

    if category:
        templates = template_dao.find_by_category(category)
    elif public_only:
        templates = template_dao.find_public_templates()
    else:
        templates = template_dao.get_with_usage_count()

    # Parse JSON fields
    for template in templates:
        if template.get('structure'):
            try:
                template['structure'] = json.loads(template['structure'])
            except (json.JSONDecodeError, TypeError):
                pass
        if template.get('placeholders'):
            try:
                template['placeholders'] = json.loads(template['placeholders'])
            except (json.JSONDecodeError, TypeError):
                pass

    return jsonify({'templates': templates}), 200


@reporting_bp.route('/templates/<int:template_id>', methods=['GET'])
@require_auth
@handle_errors
def get_report_template(template_id):
    """Get template by ID."""
    from models.dao.template_dao import TemplateDAO

    template_dao = TemplateDAO()
    template = template_dao.find_by_id(template_id)

    if not template:
        return jsonify({'error': 'Template not found'}), 404

    # Parse JSON fields
    if template.get('structure'):
        try:
            template['structure'] = json.loads(template['structure'])
        except (json.JSONDecodeError, TypeError):
            pass
    if template.get('placeholders'):
        try:
            template['placeholders'] = json.loads(template['placeholders'])
        except (json.JSONDecodeError, TypeError):
            pass

    return jsonify(template), 200


@reporting_bp.route('/templates/<int:template_id>/apply', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@handle_errors
def apply_report_template(template_id):
    """Apply template to create a new report.

    Required body:
        - engagement_id: Target engagement ID

    Optional:
        - report_name: Custom report name (defaults to template name)
    """
    from models.dao.template_dao import TemplateDAO

    data = request.get_json() or {}

    mismatch = _requested_engagement_mismatch(data)
    if mismatch:
        return mismatch
    engagement_id = g.active_engagement_id

    report_name = data.get('report_name')

    template_dao = TemplateDAO()
    try:
        report_id = template_dao.apply_to_engagement(
            template_id,
            engagement_id,
            report_name
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

    return jsonify({
        'success': True,
        'report_id': report_id,
        'engagement_id': engagement_id
    }), 201


@reporting_bp.route('/templates/<int:template_id>/preview', methods=['GET'])
@require_auth
@handle_errors
def preview_report_template(template_id):
    """Preview template with auto-populated content.

    Query params:
        - engagement_id: Engagement ID for preview data (required)
    """
    from models.dao.template_dao import TemplateDAO
    from utils.template_renderer import TemplateRenderer

    engagement_id, error = _engagement_from_request(request.args.get('engagement_id'))
    if error:
        return error

    template_dao = TemplateDAO()
    template = template_dao.find_by_id(template_id)

    if not template:
        return jsonify({'error': 'Template not found'}), 404

    # Render template with engagement data
    renderer = TemplateRenderer(g.db, engagement_id)
    rendered_sections = renderer.render_template(template['structure'])

    return jsonify({
        'template': {
            'id': template['id'],
            'name': template['name'],
            'description': template['description'],
            'category': template['category']
        },
        'sections': rendered_sections,
        'engagement_id': engagement_id
    }), 200


# ============================================
# MULTI-ENGAGEMENT COMPARISON ENDPOINTS
# ============================================

@reporting_bp.route('/compare', methods=['POST'])
@require_auth
@handle_errors
def compare_engagements():
    """Compare multiple engagements for benchmarking.

    Required body:
        - engagement_ids: Array of engagement IDs to compare (min 2)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    engagement_ids = data.get('engagement_ids', [])

    if not isinstance(engagement_ids, list) or len(engagement_ids) < 2:
        return jsonify({'error': 'At least 2 engagement IDs required'}), 400

    # Every engagement compared must be one the caller can read.
    checked_ids = []
    for raw_id in engagement_ids:
        eid, error = _engagement_from_request(raw_id if raw_id not in (None, '') else 'invalid')
        if error:
            return error
        checked_ids.append(eid)
    engagement_ids = checked_ids

    from models.dao.engagement_dao import EngagementDAO

    engagement_dao = EngagementDAO()
    cursor = g.db.cursor()

    # Gather engagement data
    comparison = {
        'engagements': [],
        'metrics': {},
        'trends': {}
    }

    for eid in engagement_ids:
        # Get engagement details
        engagement = engagement_dao.find_by_id(eid)
        if not engagement:
            continue

        # Get statistics
        stats = engagement_dao.get_statistics(eid)

        comparison['engagements'].append({
            'id': eid,
            'name': engagement['name'],
            'client': engagement.get('client_name'),
            'start_date': engagement.get('start_date'),
            'end_date': engagement.get('end_date'),
            'status': engagement.get('status'),
            'stats': stats
        })

    # Calculate comparison metrics
    comparison['metrics'] = _calculate_comparison_metrics(engagement_ids, cursor)

    # Calculate trends
    comparison['trends'] = _calculate_trends(engagement_ids, cursor)

    return jsonify(comparison), 200


def _calculate_comparison_metrics(engagement_ids: list, cursor) -> dict:
    """Calculate comparison metrics across engagements."""
    metrics = {
        'avg_findings_per_engagement': 0,
        'avg_hosts_per_engagement': 0,
        'severity_distribution': {},
        'common_findings': [],
        'tool_usage': {}
    }

    placeholders = ','.join('?' * len(engagement_ids))

    # Average findings per engagement
    cursor.execute(f'''
        SELECT AVG(finding_count) FROM (
            SELECT COUNT(*) as finding_count
            FROM engagement_findings
            WHERE engagement_id IN ({placeholders})
            GROUP BY engagement_id
        )
    ''', engagement_ids)
    row = cursor.fetchone()
    if row and row[0]:
        metrics['avg_findings_per_engagement'] = round(row[0], 2)

    # Average hosts per engagement
    cursor.execute(f'''
        SELECT AVG(host_count) FROM (
            SELECT COUNT(*) as host_count
            FROM hosts
            WHERE engagement_id IN ({placeholders})
            GROUP BY engagement_id
        )
    ''', engagement_ids)
    row = cursor.fetchone()
    if row and row[0]:
        metrics['avg_hosts_per_engagement'] = round(row[0], 2)

    # Severity distribution across all engagements
    cursor.execute(f'''
        SELECT criticality, COUNT(*) as count
        FROM engagement_findings
        WHERE engagement_id IN ({placeholders})
        GROUP BY criticality
        ORDER BY
            CASE criticality
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
            END
    ''', engagement_ids)
    for row in cursor.fetchall():
        metrics['severity_distribution'][row[0]] = row[1]

    # Common finding titles (appear in multiple engagements)
    cursor.execute(f'''
        SELECT title, COUNT(DISTINCT engagement_id) as engagement_count
        FROM engagement_findings
        WHERE engagement_id IN ({placeholders})
        GROUP BY LOWER(title)
        HAVING engagement_count > 1
        ORDER BY engagement_count DESC
        LIMIT 10
    ''', engagement_ids)
    for row in cursor.fetchall():
        metrics['common_findings'].append({
            'title': row[0],
            'engagement_count': row[1]
        })

    # Tool usage distribution
    cursor.execute(f'''
        SELECT tool_name, COUNT(*) as count
        FROM evidence
        WHERE engagement_id IN ({placeholders}) AND tool_name IS NOT NULL
        GROUP BY tool_name
        ORDER BY count DESC
    ''', engagement_ids)
    for row in cursor.fetchall():
        metrics['tool_usage'][row[0]] = row[1]

    return metrics


def _calculate_trends(engagement_ids: list, cursor) -> dict:
    """Calculate trends across engagements."""
    trends = {
        'findings_over_time': [],
        'severity_trends': {},
        'remediation_rate': 0
    }

    placeholders = ','.join('?' * len(engagement_ids))

    # Findings count by engagement (ordered by date)
    cursor.execute(f'''
        SELECT
            e.id,
            e.name,
            e.start_date,
            COUNT(f.id) as finding_count
        FROM engagements e
        LEFT JOIN engagement_findings f ON e.id = f.engagement_id
        WHERE e.id IN ({placeholders})
        GROUP BY e.id
        ORDER BY e.start_date
    ''', engagement_ids)

    for row in cursor.fetchall():
        trends['findings_over_time'].append({
            'engagement_id': row[0],
            'engagement_name': row[1],
            'date': row[2],
            'finding_count': row[3]
        })

    # Severity trends (by engagement chronologically)
    cursor.execute(f'''
        SELECT
            e.id,
            e.start_date,
            f.criticality,
            COUNT(f.id) as count
        FROM engagements e
        LEFT JOIN engagement_findings f ON e.id = f.engagement_id
        WHERE e.id IN ({placeholders})
        GROUP BY e.id, f.criticality
        ORDER BY e.start_date, f.criticality
    ''', engagement_ids)

    for row in cursor.fetchall():
        engagement_id = row[0]
        if engagement_id not in trends['severity_trends']:
            trends['severity_trends'][engagement_id] = {}
        if row[2]:  # criticality might be NULL
            trends['severity_trends'][engagement_id][row[2]] = row[3]

    return trends

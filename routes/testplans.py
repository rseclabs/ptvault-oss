"""Test Plans routes for PTVault - MITRE ATT&CK Navigator and Atomic Red Team integration."""

from flask import Blueprint, request, jsonify, g, Response
from middleware.auth import engagement_role, require_auth, require_engagement_access, require_role, can_edit_shared
from routes.engagements import require_active_engagement
from utils.error_handler import internal_error
from utils.security_headers import attachment_disposition
import json
import logging
import os

from utils.request_limits import InvalidJSONFile, JSONFileTooLarge, load_json_upload
from models.engagement_cleanup import delete_test_plan

testplans_bp = Blueprint('testplans', __name__, url_prefix='/api/testplans')


# ============================================
# PLAN SCOPE HELPERS
# ============================================
# A plan with engagement_id IS NULL is a reusable template; otherwise it
# belongs to exactly one engagement and is only visible while that
# engagement is active.

EXECUTION_STATUSES = ('pending', 'in_progress', 'completed', 'failed', 'skipped')
# Ordered strongest to weakest detection; NULL in the DB = not evaluated
EXECUTION_OUTCOMES = ('prevented', 'alerted', 'logged', 'not_detected')


def _row_to_plan(cursor, row):
    plan = dict(zip([d[0] for d in cursor.description], row))
    plan['is_template'] = plan.get('engagement_id') is None
    return plan


def _get_accessible_plan(cursor, plan_id):
    """Return the plan if it is a template or belongs to the active engagement."""
    cursor.execute("""
        SELECT * FROM test_plans
        WHERE id = ? AND (engagement_id IS NULL OR engagement_id = ?)
    """, (plan_id, g.get('active_engagement_id')))
    row = cursor.fetchone()
    return _row_to_plan(cursor, row) if row else None


def _plan_write_denied(plan):
    """Return a 403 response unless the user may change this plan, else None.

    An engagement's plan needs the editor role on that engagement; a global
    template can be changed only by its creator or an admin.
    """
    if plan['engagement_id'] is None:
        allowed = can_edit_shared(plan.get('created_by'))
    else:
        role = engagement_role(g.db, g.current_user, g.current_user_role, plan['engagement_id'])
        allowed = role in ('editor', 'owner')
    if allowed:
        return None
    return jsonify({"error": "insufficient permissions"}), 403


def _plan_create_denied(engagement_id):
    """Return a 403 response unless the user may create a plan here, else None.

    A template (engagement_id None) needs a global admin or tester; a plan in
    an engagement needs the editor role on it.
    """
    if engagement_id is None:
        allowed = g.current_user_role in ('admin', 'tester')
    else:
        role = engagement_role(g.db, g.current_user, g.current_user_role, engagement_id)
        allowed = role in ('editor', 'owner')
    if allowed:
        return None
    return jsonify({"error": "insufficient permissions"}), 403


def _copy_plan(cursor, source, engagement_id, name):
    """Copy a plan and its items. Returns the new plan id."""
    source_template_id = source['id'] if source.get('engagement_id') is None else source.get('source_template_id')
    if engagement_id is None:
        source_template_id = None
    cursor.execute("""
        INSERT INTO test_plans (name, description, target_platform, tags,
                                engagement_id, source_template_id, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, source.get('description'), source.get('target_platform'),
          source.get('tags'), engagement_id, source_template_id, g.current_user))
    new_plan_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO test_plan_items (test_plan_id, atomic_id, custom_name, custom_command,
                                    custom_platform, sort_order, enabled, input_overrides, notes)
        SELECT ?, atomic_id, custom_name, custom_command, custom_platform,
               sort_order, enabled, input_overrides, notes
        FROM test_plan_items
        WHERE test_plan_id = ?
        ORDER BY sort_order, id
    """, (new_plan_id, source['id']))
    return new_plan_id


def _plan_with_count(cursor, plan_id):
    cursor.execute("""
        SELECT tp.*, COUNT(tpi.id) as item_count,
               SUM(CASE WHEN tpi.atomic_id IS NOT NULL AND a.id IS NULL THEN 1 ELSE 0 END) as missing_count
        FROM test_plans tp
        LEFT JOIN test_plan_items tpi ON tp.id = tpi.test_plan_id
        LEFT JOIN atomics a ON a.id = tpi.atomic_id
        WHERE tp.id = ?
        GROUP BY tp.id
    """, (plan_id,))
    return _row_to_plan(cursor, cursor.fetchone())


# ============================================
# ATOMICS LIBRARY ENDPOINTS
# ============================================

@testplans_bp.route('/atomics/status', methods=['GET'])
@require_auth
def get_atomics_status():
    """
    Get the status of the Atomic Red Team library.
    Returns: installed status, version, total techniques/tests, last updated
    """
    try:
        cursor = g.db.cursor()

        # Check if atomics_metadata exists and has data
        cursor.execute("SELECT * FROM atomics_metadata WHERE id = 1")
        row = cursor.fetchone()

        if not row:
            return jsonify({
                "installed": False,
                "version": None,
                "last_updated": None,
                "total_techniques": 0,
                "total_tests": 0,
                "download_path": None
            }), 200

        columns = [desc[0] for desc in cursor.description]
        metadata = dict(zip(columns, row))
        metadata["installed"] = True

        return jsonify(metadata), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/atomics/download', methods=['POST'])
@require_auth
@require_role('admin')
def download_atomics():
    """
    Download and parse the Atomic Red Team repository with progress streaming.
    Uses newline-delimited JSON for better Flask dev server compatibility.
    """
    from flask import stream_with_context
    from utils.atomics_downloader import download_and_parse_atomics_with_progress
    from models.database import get_db_connection

    def generate():
        # Need a fresh connection for the generator context
        db_conn = get_db_connection()
        try:
            for progress in download_and_parse_atomics_with_progress(db_conn):
                # Use newline-delimited JSON with padding for better streaming
                data = json.dumps(progress) + '\n'
                yield data
        except Exception as e:
            logging.getLogger(__name__).exception('Atomics download failed')
            yield json.dumps({'stage': 'error', 'error': 'Atomics download failed; see the server log'}) + '\n'
        finally:
            db_conn.close()

    response = Response(
        stream_with_context(generate()),
        mimetype='application/x-ndjson',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Accel-Buffering': 'no',
            'Transfer-Encoding': 'chunked'
        }
    )
    response.implicit_sequence_conversion = False
    return response


@testplans_bp.route('/atomics', methods=['GET'])
@require_auth
def list_atomics():
    """
    List atomics with optional filters.
    Query params:
        - technique: Filter by technique_id (e.g., T1059.001)
        - platform: Filter by platform (windows, linux, macos)
        - tactic: Filter by tactic
        - executor: Filter by executor type
        - search: Search in name, technique_id, description
        - limit: Max results (default 100)
        - offset: Pagination offset
    """
    try:
        cursor = g.db.cursor()

        query = "SELECT * FROM atomics WHERE 1=1"
        params = []

        # Filter by technique
        technique = request.args.get('technique')
        if technique:
            query += " AND technique_id = ?"
            params.append(technique)

        # Filter by platform
        platform = request.args.get('platform')
        if platform:
            query += " AND supported_platforms LIKE ?"
            params.append(f'%"{platform}"%')

        # Filter by tactic
        tactic = request.args.get('tactic')
        if tactic:
            query += " AND tactic = ?"
            params.append(tactic)

        # Filter by executor
        executor = request.args.get('executor')
        if executor:
            query += " AND executor_name = ?"
            params.append(executor)

        # Search
        search = request.args.get('search')
        if search:
            query += " AND (technique_id LIKE ? OR technique_name LIKE ? OR atomic_test_name LIKE ? OR description LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        query += " ORDER BY technique_id, atomic_test_index"

        # Pagination
        limit = max(1, min(request.args.get('limit', 100, type=int), 1000))
        offset = max(0, request.args.get('offset', 0, type=int))
        query += " LIMIT ? OFFSET ?"

        cursor.execute(query, params + [limit, offset])
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        atomics = []
        for row in rows:
            atomic = dict(zip(columns, row))
            # Parse JSON fields
            for field in ['supported_platforms', 'input_arguments', 'dependencies']:
                if atomic.get(field):
                    try:
                        atomic[field] = json.loads(atomic[field])
                    except json.JSONDecodeError:
                        atomic[field] = None
            atomics.append(atomic)

        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM atomics WHERE 1=1"
        cursor.execute(count_query.replace("SELECT COUNT(*)", "SELECT COUNT(*)"))
        # Re-run with same filters but no limit
        count_query = query.replace("SELECT *", "SELECT COUNT(*)").split(" LIMIT")[0]
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        return jsonify({
            "atomics": atomics,
            "total": total,
            "limit": limit,
            "offset": offset
        }), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/atomics/<int:atomic_id>', methods=['GET'])
@require_auth
def get_atomic(atomic_id):
    """Get a single atomic test by ID with full details."""
    try:
        cursor = g.db.cursor()
        cursor.execute("SELECT * FROM atomics WHERE id = ?", (atomic_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Atomic not found"}), 404

        columns = [desc[0] for desc in cursor.description]
        atomic = dict(zip(columns, row))

        # Parse JSON fields
        for field in ['supported_platforms', 'input_arguments', 'dependencies']:
            if atomic.get(field):
                try:
                    atomic[field] = json.loads(atomic[field])
                except json.JSONDecodeError:
                    atomic[field] = None

        return jsonify(atomic), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/atomics/techniques', methods=['GET'])
@require_auth
def list_techniques():
    """
    Get unique techniques with test counts.
    Useful for the technique browser UI.
    """
    try:
        cursor = g.db.cursor()
        cursor.execute("""
            SELECT technique_id, technique_name, tactic, COUNT(*) as test_count
            FROM atomics
            GROUP BY technique_id
            ORDER BY technique_id
        """)
        rows = cursor.fetchall()

        techniques = [{
            "technique_id": row[0],
            "technique_name": row[1],
            "tactic": row[2],
            "test_count": row[3]
        } for row in rows]

        return jsonify(techniques), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/atomics/tactics', methods=['GET'])
@require_auth
def list_tactics():
    """Get unique tactics with technique counts."""
    try:
        cursor = g.db.cursor()
        cursor.execute("""
            SELECT tactic, COUNT(DISTINCT technique_id) as technique_count
            FROM atomics
            WHERE tactic IS NOT NULL
            GROUP BY tactic
            ORDER BY tactic
        """)
        rows = cursor.fetchall()

        tactics = [{
            "tactic": row[0],
            "technique_count": row[1]
        } for row in rows]

        return jsonify(tactics), 200

    except Exception as e:
        return internal_error(e)


# ============================================
# NAVIGATOR LAYER ENDPOINTS
# ============================================

@testplans_bp.route('/layers', methods=['GET'])
@require_auth
def list_layers():
    """List all imported Navigator layers."""
    try:
        cursor = g.db.cursor()
        cursor.execute("""
            SELECT id, name, description, domain, technique_count, created_at
            FROM navigator_layers
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        layers = [dict(zip(columns, row)) for row in rows]

        return jsonify(layers), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/layers/import', methods=['POST'])
@require_auth
@require_role('admin', 'tester')
def import_layer():
    """
    Import a MITRE ATT&CK Navigator layer JSON file.
    Accepts multipart/form-data with 'file' field.
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if not file.filename.endswith('.json'):
            return jsonify({"error": "File must be a JSON file"}), 400

        # Read and parse JSON
        try:
            layer_data = load_json_upload(file)          # capped before parsing (M-18)
        except JSONFileTooLarge as e:
            return jsonify({"error": str(e)}), 413
        except InvalidJSONFile as e:
            return jsonify({"error": f"Invalid JSON: {e}"}), 400
        if not isinstance(layer_data, dict):
            return jsonify({"error": "Invalid Navigator layer: expected a JSON object"}), 400

        # Validate layer structure
        if 'techniques' not in layer_data:
            return jsonify({"error": "Invalid Navigator layer: missing 'techniques' field"}), 400

        name = layer_data.get('name', file.filename.replace('.json', ''))
        description = layer_data.get('description', '')
        domain = layer_data.get('domain', 'enterprise-attack')
        technique_count = len(layer_data.get('techniques', []))

        cursor = g.db.cursor()
        cursor.execute("""
            INSERT INTO navigator_layers (name, description, domain, layer_json, technique_count, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, description, domain, json.dumps(layer_data), technique_count, g.current_user))
        g.db.commit()

        layer_id = cursor.lastrowid

        return jsonify({
            "id": layer_id,
            "name": name,
            "description": description,
            "domain": domain,
            "technique_count": technique_count,
            "message": f"Successfully imported layer with {technique_count} techniques"
        }), 201

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/layers/<int:layer_id>', methods=['GET'])
@require_auth
def get_layer(layer_id):
    """Get a layer with full technique details."""
    try:
        cursor = g.db.cursor()
        cursor.execute("SELECT * FROM navigator_layers WHERE id = ?", (layer_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Layer not found"}), 404

        columns = [desc[0] for desc in cursor.description]
        layer = dict(zip(columns, row))

        # Parse layer_json
        if layer.get('layer_json'):
            try:
                layer['layer_data'] = json.loads(layer['layer_json'])
                del layer['layer_json']  # Don't send raw JSON string
            except json.JSONDecodeError:
                layer['layer_data'] = None

        return jsonify(layer), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/layers/<int:layer_id>', methods=['DELETE'])
@require_auth
@require_role('admin', 'tester')
def delete_layer(layer_id):
    """Delete an imported layer."""
    try:
        cursor = g.db.cursor()
        cursor.execute("SELECT created_by FROM navigator_layers WHERE id = ?", (layer_id,))
        layer = cursor.fetchone()
        if not layer:
            return jsonify({"error": "Layer not found"}), 404
        if not can_edit_shared(layer[0]):
            return jsonify({"error": "only the creator or an admin can change this"}), 403

        cursor.execute("DELETE FROM navigator_layers WHERE id = ?", (layer_id,))
        g.db.commit()

        return jsonify({"message": "Layer deleted"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/layers/<int:layer_id>/match', methods=['POST'])
@require_auth
def match_layer_to_atomics(layer_id):
    """
    Match layer techniques to available atomics.
    Request body:
        - min_score: Minimum score to include (default 0)
        - colors: List of colors to filter by (optional)
        - platform: Filter atomics by platform (optional)
    Returns matched atomics ready for test plan creation.
    """
    try:
        cursor = g.db.cursor()

        # Get layer
        cursor.execute("SELECT layer_json FROM navigator_layers WHERE id = ?", (layer_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Layer not found"}), 404

        layer_data = json.loads(row[0])
        techniques = layer_data.get('techniques', [])

        # Get filter params
        data = request.get_json() or {}
        min_score = data.get('min_score', 0)
        filter_colors = data.get('colors', [])
        platform = data.get('platform')

        # Filter techniques from layer
        filtered_technique_ids = []
        for tech in techniques:
            technique_id = tech.get('techniqueID', '')
            score = tech.get('score', 0) or 0
            color = tech.get('color', '')

            # Apply filters
            if score < min_score:
                continue
            if filter_colors and color not in filter_colors:
                continue

            filtered_technique_ids.append(technique_id)

        if not filtered_technique_ids:
            return jsonify({
                "matched_atomics": [],
                "total_matched": 0,
                "message": "No techniques matched the filter criteria"
            }), 200

        # Find matching atomics
        placeholders = ','.join(['?' for _ in filtered_technique_ids])
        query = f"SELECT * FROM atomics WHERE technique_id IN ({placeholders})"
        params = filtered_technique_ids

        if platform:
            query += " AND supported_platforms LIKE ?"
            params.append(f'%"{platform}"%')

        query += " ORDER BY technique_id, atomic_test_index"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        matched_atomics = []
        for row in rows:
            atomic = dict(zip(columns, row))
            # Parse JSON fields
            for field in ['supported_platforms', 'input_arguments', 'dependencies']:
                if atomic.get(field):
                    try:
                        atomic[field] = json.loads(atomic[field])
                    except json.JSONDecodeError:
                        atomic[field] = None
            matched_atomics.append(atomic)

        return jsonify({
            "matched_atomics": matched_atomics,
            "total_matched": len(matched_atomics),
            "techniques_in_layer": len(filtered_technique_ids),
            "message": f"Found {len(matched_atomics)} atomics for {len(filtered_technique_ids)} techniques"
        }), 200

    except Exception as e:
        return internal_error(e)


# ============================================
# TEST PLAN CRUD ENDPOINTS
# ============================================

@testplans_bp.route('/plans', methods=['GET'])
@require_auth
def list_plans():
    """
    List templates plus the active engagement's plans.
    Each plan carries `is_template`. Query param `scope`:
        - all (default): templates + active engagement plans
        - engagement: only the active engagement's plans
        - templates: only templates
    """
    try:
        scope = request.args.get('scope', 'all')
        engagement_id = g.get('active_engagement_id')

        if scope == 'templates':
            where, params = "tp.engagement_id IS NULL", []
        elif scope == 'engagement':
            where, params = "tp.engagement_id = ?", [engagement_id]
        else:
            where, params = "(tp.engagement_id IS NULL OR tp.engagement_id = ?)", [engagement_id]

        cursor = g.db.cursor()
        cursor.execute(f"""
            SELECT tp.*, COUNT(tpi.id) as item_count,
                   SUM(CASE WHEN tpi.atomic_id IS NOT NULL AND a.id IS NULL THEN 1 ELSE 0 END) as missing_count
            FROM test_plans tp
            LEFT JOIN test_plan_items tpi ON tp.id = tpi.test_plan_id
            LEFT JOIN atomics a ON a.id = tpi.atomic_id
            WHERE {where}
            GROUP BY tp.id
            ORDER BY tp.updated_at DESC, tp.id DESC
        """, params)
        rows = cursor.fetchall()

        plans = [_row_to_plan(cursor, row) for row in rows]

        # Run progress in the active engagement (engagement plans only)
        progress = {}
        if engagement_id:
            cursor.execute("""
                SELECT test_plan_id, COUNT(*),
                       SUM(CASE WHEN status != 'pending' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN outcome IS NOT NULL THEN 1 ELSE 0 END)
                FROM test_executions WHERE engagement_id = ?
                GROUP BY test_plan_id
            """, (engagement_id,))
            progress = {r[0]: (r[1], r[2] or 0, r[3] or 0) for r in cursor.fetchall()}
        for plan in plans:
            total, done, evaluated = progress.get(plan['id'], (0, 0, 0))
            plan.update(exec_total=total, exec_done=done, exec_evaluated=evaluated)

        return jsonify(plans), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/plans', methods=['POST'])
@require_auth
def create_plan():
    """
    Create a new test plan.
    Request body:
        - name: Plan name (required)
        - description: Description (optional)
        - target_platform: windows, linux, macos, all (default: all)
        - tags: Comma-separated tags (optional)
        - is_template: true to create a reusable template; otherwise the
          plan belongs to the active engagement (default: false)
    """
    try:
        data = request.get_json() or {}

        if not data.get('name'):
            return jsonify({"error": "Name is required"}), 400

        if data.get('is_template'):
            engagement_id = None
        else:
            engagement_id = g.get('active_engagement_id')
            if not engagement_id:
                return jsonify({"error": "Select an engagement first, or create a template"}), 400

        denied = _plan_create_denied(engagement_id)
        if denied:
            return denied

        cursor = g.db.cursor()
        cursor.execute("""
            INSERT INTO test_plans (name, description, target_platform, tags, engagement_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data['name'],
            data.get('description', ''),
            data.get('target_platform', 'all'),
            data.get('tags', ''),
            engagement_id,
            g.current_user
        ))
        g.db.commit()

        plan = _plan_with_count(cursor, cursor.lastrowid)

        return jsonify(plan), 201

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>', methods=['GET'])
@require_auth
def get_plan(plan_id):
    """Get a test plan with all its items."""
    try:
        cursor = g.db.cursor()

        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404

        # Get items with atomic details
        cursor.execute("""
            SELECT tpi.*,
                   a.technique_id, a.technique_name, a.atomic_test_name,
                   a.description as atomic_description, a.supported_platforms,
                   a.executor_name, a.executor_command, a.executor_cleanup,
                   a.input_arguments, a.elevation_required,
                   a.id as atomic_found
            FROM test_plan_items tpi
            LEFT JOIN atomics a ON tpi.atomic_id = a.id
            WHERE tpi.test_plan_id = ?
            ORDER BY tpi.sort_order
        """, (plan_id,))

        item_rows = cursor.fetchall()
        item_columns = [desc[0] for desc in cursor.description]

        items = []
        for item_row in item_rows:
            item = dict(zip(item_columns, item_row))
            # Item points at an atomic that is no longer in the library
            item['atomic_missing'] = item['atomic_id'] is not None and item.pop('atomic_found') is None
            item.pop('atomic_found', None)
            # Parse JSON fields
            for field in ['supported_platforms', 'input_arguments', 'input_overrides']:
                if item.get(field):
                    try:
                        item[field] = json.loads(item[field])
                    except json.JSONDecodeError:
                        item[field] = None
            items.append(item)

        plan['items'] = items

        return jsonify(plan), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>', methods=['PUT'])
@require_auth
def update_plan(plan_id):
    """Update a test plan."""
    try:
        data = request.get_json()

        cursor = g.db.cursor()

        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        denied = _plan_write_denied(plan)
        if denied:
            return denied

        cursor.execute("""
            UPDATE test_plans
            SET name = COALESCE(?, name),
                description = COALESCE(?, description),
                target_platform = COALESCE(?, target_platform),
                tags = COALESCE(?, tags),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            data.get('name'),
            data.get('description'),
            data.get('target_platform'),
            data.get('tags'),
            plan_id
        ))
        g.db.commit()

        return jsonify(_plan_with_count(cursor, plan_id)), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>', methods=['DELETE'])
@require_auth
def delete_plan(plan_id):
    """Delete a test plan and all its items (executions of it are deleted too)."""
    try:
        cursor = g.db.cursor()
        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        denied = _plan_write_denied(plan)
        if denied:
            return denied
        delete_test_plan(cursor, plan_id)          # items and executions too (L-24)
        g.db.commit()

        return jsonify({"message": "Test plan deleted"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>/duplicate', methods=['POST'])
@require_auth
def duplicate_plan(plan_id):
    """
    Copy a test plan with all its items.
    Request body (optional):
        - target: 'engagement' (copy into the active engagement),
                  'template' (save as a reusable template),
                  or omitted (same scope as the source)
        - name: name for the copy
    Copying a template into an engagement keeps its name ("use template");
    any other copy gets a " (Copy)" suffix by default.
    """
    try:
        data = request.get_json(silent=True) or {}
        target = data.get('target')
        if target not in (None, 'engagement', 'template'):
            return jsonify({"error": "target must be 'engagement' or 'template'"}), 400

        cursor = g.db.cursor()

        original = _get_accessible_plan(cursor, plan_id)
        if not original:
            return jsonify({"error": "Test plan not found"}), 404

        if target is None:
            target = 'template' if original['is_template'] else 'engagement'

        if target == 'engagement':
            engagement_id = g.get('active_engagement_id')
            if not engagement_id:
                return jsonify({"error": "Select an engagement first"}), 400
        else:
            engagement_id = None

        denied = _plan_create_denied(engagement_id)
        if denied:
            return denied

        default_name = original['name'] if (original['is_template'] and target == 'engagement') \
            else f"{original['name']} (Copy)"
        new_name = (data.get('name') or '').strip() or default_name

        new_plan_id = _copy_plan(cursor, original, engagement_id, new_name)
        g.db.commit()

        return jsonify(_plan_with_count(cursor, new_plan_id)), 201

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


# ============================================
# TEST PLAN ITEMS ENDPOINTS
# ============================================

@testplans_bp.route('/plans/<int:plan_id>/items', methods=['POST'])
@require_auth
def add_plan_item(plan_id):
    """
    Add an item to a test plan.
    Request body:
        - atomic_id: ID of atomic to add (for library items)
        OR
        - custom_name: Name for custom test
        - custom_command: Command for custom test
        - custom_platform: Platform for custom test

        Optional:
        - input_overrides: JSON object overriding default arguments
        - notes: User notes
    """
    try:
        cursor = g.db.cursor()

        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        denied = _plan_write_denied(plan)
        if denied:
            return denied

        data = request.get_json()

        # Get next sort order
        cursor.execute("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM test_plan_items WHERE test_plan_id = ?
        """, (plan_id,))
        sort_order = cursor.fetchone()[0]

        # Handle input_overrides
        input_overrides = data.get('input_overrides')
        if input_overrides and isinstance(input_overrides, dict):
            input_overrides = json.dumps(input_overrides)

        atomic_id = data.get('atomic_id')

        cursor.execute("""
            INSERT INTO test_plan_items (test_plan_id, atomic_id, custom_name, custom_command,
                                        custom_platform, sort_order, enabled, input_overrides, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plan_id,
            atomic_id,
            data.get('custom_name'),
            data.get('custom_command'),
            data.get('custom_platform'),
            sort_order,
            1,  # enabled by default
            input_overrides,
            data.get('notes'),
        ))

        # Update plan's updated_at
        cursor.execute("UPDATE test_plans SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_id,))
        g.db.commit()

        item_id = cursor.lastrowid

        # Return the new item with atomic details
        cursor.execute("""
            SELECT tpi.*,
                   a.technique_id, a.technique_name, a.atomic_test_name,
                   a.description as atomic_description, a.supported_platforms,
                   a.executor_name, a.executor_command
            FROM test_plan_items tpi
            LEFT JOIN atomics a ON tpi.atomic_id = a.id
            WHERE tpi.id = ?
        """, (item_id,))

        row = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description]
        item = dict(zip(columns, row))

        return jsonify(item), 201

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>/items/<int:item_id>', methods=['PUT'])
@require_auth
def update_plan_item(plan_id, item_id):
    """Update a test plan item."""
    try:
        data = request.get_json()
        cursor = g.db.cursor()

        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        denied = _plan_write_denied(plan)
        if denied:
            return denied

        # Verify item exists and belongs to plan
        cursor.execute("""
            SELECT id FROM test_plan_items WHERE id = ? AND test_plan_id = ?
        """, (item_id, plan_id))
        if not cursor.fetchone():
            return jsonify({"error": "Item not found"}), 404

        # Handle input_overrides
        input_overrides = data.get('input_overrides')
        if input_overrides is not None:
            if isinstance(input_overrides, dict):
                input_overrides = json.dumps(input_overrides)

        # Marking an item reviewed after an Atomics refresh changed its test (M-6)
        if data.get('reviewed') is True:
            cursor.execute("UPDATE test_plan_items SET needs_review = 0 WHERE id = ?", (item_id,))

        cursor.execute("""
            UPDATE test_plan_items
            SET enabled = COALESCE(?, enabled),
                input_overrides = COALESCE(?, input_overrides),
                notes = COALESCE(?, notes),
                custom_name = COALESCE(?, custom_name),
                custom_command = COALESCE(?, custom_command)
            WHERE id = ?
        """, (
            data.get('enabled'),
            input_overrides,
            data.get('notes'),
            data.get('custom_name'),
            data.get('custom_command'),
            item_id
        ))

        # Update plan's updated_at
        cursor.execute("UPDATE test_plans SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_id,))
        g.db.commit()

        return jsonify({"message": "Item updated"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>/items/<int:item_id>', methods=['DELETE'])
@require_auth
def delete_plan_item(plan_id, item_id):
    """Remove an item from a test plan."""
    try:
        cursor = g.db.cursor()
        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        denied = _plan_write_denied(plan)
        if denied:
            return denied
        cursor.execute("""
            DELETE FROM test_plan_items WHERE id = ? AND test_plan_id = ?
        """, (item_id, plan_id))

        if cursor.rowcount == 0:
            return jsonify({"error": "Item not found"}), 404

        # Update plan's updated_at
        cursor.execute("UPDATE test_plans SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_id,))
        g.db.commit()

        return jsonify({"message": "Item removed"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>/items/reorder', methods=['POST'])
@require_auth
def reorder_plan_items(plan_id):
    """
    Reorder items in a test plan.
    Request body:
        - item_ids: Array of item IDs in new order
    """
    try:
        data = request.get_json()
        item_ids = data.get('item_ids', [])

        if not item_ids:
            return jsonify({"error": "item_ids array required"}), 400

        cursor = g.db.cursor()
        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        denied = _plan_write_denied(plan)
        if denied:
            return denied

        # Update sort_order for each item
        for idx, item_id in enumerate(item_ids):
            cursor.execute("""
                UPDATE test_plan_items
                SET sort_order = ?
                WHERE id = ? AND test_plan_id = ?
            """, (idx, item_id, plan_id))

        # Update plan's updated_at
        cursor.execute("UPDATE test_plans SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_id,))
        g.db.commit()

        return jsonify({"message": "Items reordered"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/plans/<int:plan_id>/items/bulk', methods=['POST'])
@require_auth
def add_bulk_items(plan_id):
    """
    Add multiple items to a test plan at once.
    Request body:
        - atomic_ids: Array of atomic IDs to add
    """
    try:
        cursor = g.db.cursor()

        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        denied = _plan_write_denied(plan)
        if denied:
            return denied

        data = request.get_json()
        atomic_ids = data.get('atomic_ids', [])

        if not atomic_ids:
            return jsonify({"error": "atomic_ids array required"}), 400

        # Get next sort order
        cursor.execute("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM test_plan_items WHERE test_plan_id = ?
        """, (plan_id,))
        sort_order = cursor.fetchone()[0]

        added = 0
        for atomic_id in atomic_ids:
            cursor.execute("""
                INSERT INTO test_plan_items (test_plan_id, atomic_id, sort_order, enabled)
                VALUES (?, ?, ?, 1)
            """, (plan_id, atomic_id, sort_order))
            sort_order += 1
            added += 1

        # Update plan's updated_at
        cursor.execute("UPDATE test_plans SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_id,))
        g.db.commit()

        return jsonify({"message": f"Added {added} items to plan"}), 201

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


# ============================================
# SCRIPT GENERATION ENDPOINTS
# ============================================

@testplans_bp.route('/plans/<int:plan_id>/script', methods=['GET'])
@require_auth
def generate_script_endpoint(plan_id):
    """
    Generate an executable script from a test plan.
    Query params:
        - platform: windows, linux, macos (required)
        - include_readme: true/false (default: true) - whether to return zip with README
    Returns the script as a downloadable file (zip if include_readme=true).
    """
    try:
        platform = request.args.get('platform', 'linux')
        include_readme = request.args.get('include_readme', 'true').lower() == 'true'

        cursor = g.db.cursor()

        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404

        # Get enabled items with atomic details
        cursor.execute("""
            SELECT tpi.*,
                   a.technique_id, a.technique_name, a.atomic_test_name,
                   a.executor_command, a.executor_cleanup, a.input_arguments,
                   a.supported_platforms, a.elevation_required
            FROM test_plan_items tpi
            LEFT JOIN atomics a ON tpi.atomic_id = a.id
            WHERE tpi.test_plan_id = ? AND tpi.enabled = 1
              -- skip items whose atomic is no longer in the library
              AND (tpi.atomic_id IS NULL OR a.id IS NOT NULL)
            ORDER BY tpi.sort_order
        """, (plan_id,))

        item_rows = cursor.fetchall()
        item_columns = [desc[0] for desc in cursor.description]
        items = [dict(zip(item_columns, row)) for row in item_rows]

        # An Atomics refresh changed what these tests run; a person has to look first (M-6)
        changed = [item for item in items if item.get('needs_review')]
        if changed:
            names = ', '.join(item.get('custom_name') or item.get('atomic_test_name') or f"item {item['id']}"
                              for item in changed[:5])
            return jsonify({
                "error": f"{len(changed)} test(s) changed in the last Atomics refresh and need review "
                         f"before a script can be generated: {names}",
                "needs_review": [item['id'] for item in changed],
            }), 409

        if not items:
            cursor.execute("""
                SELECT COUNT(*) FROM test_plan_items tpi
                LEFT JOIN atomics a ON tpi.atomic_id = a.id
                WHERE tpi.test_plan_id = ? AND tpi.enabled = 1
                  AND tpi.atomic_id IS NOT NULL AND a.id IS NULL
            """, (plan_id,))
            if cursor.fetchone()[0]:
                return jsonify({"error": "Every enabled test in this plan is missing from the Atomics library. "
                                         "Rebuild the plan or re-add its tests from the library."}), 400
            return jsonify({"error": "No enabled items in test plan"}), 400

        # Generate script based on platform
        from utils.script_generator import (
            generate_script, get_script_filename,
            generate_readme, get_readme_filename
        )

        script_platform = 'powershell' if platform == 'windows' else 'bash'
        script_content = generate_script(plan, items, script_platform)
        script_filename = get_script_filename(plan['name'], script_platform)

        if include_readme:
            # Generate README and return as zip
            import io
            import zipfile
            import re

            readme_content = generate_readme(plan, items, script_platform)

            # Create zip in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(script_filename, script_content)
                zf.writestr('README.md', readme_content)

            zip_buffer.seek(0)

            # Generate zip filename
            safe_name = re.sub(r'[^\w\s-]', '', plan['name'])
            safe_name = re.sub(r'[-\s]+', '_', safe_name).strip('_') or 'test_plan'
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f"{safe_name}_{timestamp}.zip"

            return Response(
                zip_buffer.getvalue(),
                mimetype='application/zip',
                headers={
                    'Content-Disposition': attachment_disposition(zip_filename, 'test_plan.zip')
                }
            )
        else:
            # Return just the script
            return Response(
                script_content,
                mimetype='text/plain',
                headers={
                    'Content-Disposition': attachment_disposition(script_filename, 'test_plan.sh')
                }
            )

    except Exception as e:
        return internal_error(e)


def _generate_basic_script(plan, items, platform):
    """Basic script generation fallback."""
    if platform == 'windows':
        lines = [
            f"# PTVault Test Plan: {plan['name']}",
            f"# Generated script - Platform: Windows",
            "# WARNING: Review commands before running in production",
            "",
            "$TestResults = @{}",
            "",
        ]

        for idx, item in enumerate(items, 1):
            name = item.get('atomic_test_name') or item.get('custom_name') or f'Test {idx}'
            technique = item.get('technique_id', 'Custom')
            command = item.get('executor_command') or item.get('custom_command') or '# No command'

            lines.append(f"# Test {idx}: {technique} - {name}")
            lines.append(f"Write-Host '[*] Running: {name}' -ForegroundColor Cyan")
            lines.append("try {")
            lines.append(f"    {command}")
            lines.append(f"    $TestResults['{idx}'] = 'PASS'")
            lines.append("    Write-Host '[+] Test completed' -ForegroundColor Green")
            lines.append("} catch {")
            lines.append(f"    $TestResults['{idx}'] = 'FAIL'")
            lines.append("    Write-Host '[-] Test failed' -ForegroundColor Red")
            lines.append("}")
            lines.append("")

        lines.append("Write-Host 'Test execution complete'")
        lines.append("$TestResults | Format-Table")

        return '\n'.join(lines)
    else:
        lines = [
            "#!/bin/bash",
            f"# PTVault Test Plan: {plan['name']}",
            f"# Generated script - Platform: {platform}",
            "# WARNING: Review commands before running in production",
            "",
            "declare -A TEST_RESULTS",
            "",
        ]

        for idx, item in enumerate(items, 1):
            name = item.get('atomic_test_name') or item.get('custom_name') or f'Test {idx}'
            technique = item.get('technique_id', 'Custom')
            command = item.get('executor_command') or item.get('custom_command') or '# No command'

            lines.append(f"# Test {idx}: {technique} - {name}")
            lines.append(f'echo "[*] Running: {name}"')
            lines.append(f"if {command}; then")
            lines.append(f"    TEST_RESULTS[{idx}]='PASS'")
            lines.append('    echo "[+] Test completed"')
            lines.append("else")
            lines.append(f"    TEST_RESULTS[{idx}]='FAIL'")
            lines.append('    echo "[-] Test failed"')
            lines.append("fi")
            lines.append("")

        lines.append('echo "Test execution complete"')
        lines.append('for key in "${!TEST_RESULTS[@]}"; do echo "Test $key: ${TEST_RESULTS[$key]}"; done')

        return '\n'.join(lines)


# ============================================
# EXECUTION TRACKING ENDPOINTS
# ============================================

@testplans_bp.route('/executions', methods=['GET'])
@require_auth
@require_active_engagement
def list_executions():
    """List test executions for the current engagement."""
    try:
        cursor = g.db.cursor()

        cursor.execute("""
            SELECT te.*,
                   tp.name as plan_name,
                   tpi.atomic_id,
                   a.technique_id as technique_id,
                   COALESCE(a.atomic_test_name, tpi.custom_name) as atomic_test_name,
                   tpi.custom_name,
                   h.ip as host_ip, h.hostname as host_hostname,
                   tpi.sort_order as item_sort_order, a.tactic as tactic,
                   ev.title as evidence_title
            FROM test_executions te
            JOIN test_plans tp ON te.test_plan_id = tp.id
            JOIN test_plan_items tpi ON te.test_plan_item_id = tpi.id
            LEFT JOIN atomics a ON tpi.atomic_id = a.id
            LEFT JOIN hosts h ON te.host_id = h.id
            LEFT JOIN evidence ev ON te.evidence_id = ev.id
            WHERE te.engagement_id = ?
            ORDER BY te.created_at DESC
        """, (g.active_engagement_id,))

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        executions = [dict(zip(columns, row)) for row in rows]

        return jsonify(executions), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/executions/start', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
def start_execution():
    """
    Start a test plan execution for the current engagement.
    Creates execution records for all enabled items in the plan.
    Request body:
        - plan_id: ID of the test plan to execute
        - host_id: Optional target host ID
    If plan_id is a template, it is first copied into the active engagement
    and the copy is executed, so templates never accumulate execution history.
    Response includes the plan_id that was actually executed.
    """
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')
        host_id = data.get('host_id')

        if not plan_id:
            return jsonify({"error": "plan_id is required"}), 400

        cursor = g.db.cursor()

        # Target host must belong to the active engagement and be in scope
        if host_id:
            cursor.execute(
                "SELECT out_of_scope FROM hosts WHERE id = ? AND engagement_id = ?",
                (host_id, g.active_engagement_id)
            )
            host_row = cursor.fetchone()
            if not host_row:
                return jsonify({"error": "Host not found in the active engagement"}), 400
            if host_row[0]:
                return jsonify({"error": "Host is marked out of scope"}), 400

        plan = _get_accessible_plan(cursor, plan_id)
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404

        # One run per (plan, host): the grid has one column per host
        if not plan['is_template']:
            cursor.execute("""
                SELECT 1 FROM test_executions
                WHERE engagement_id = ? AND test_plan_id = ? AND host_id IS ?
                LIMIT 1
            """, (g.active_engagement_id, plan_id, host_id or None))
            if cursor.fetchone():
                target = "this host" if host_id else "no specific host"
                return jsonify({"error": f"This plan has already been run against {target}"}), 409

        # Get enabled items for the plan
        cursor.execute("""
            SELECT id FROM test_plan_items WHERE test_plan_id = ? AND enabled = 1
            ORDER BY sort_order
        """, (plan_id,))
        items = cursor.fetchall()

        if not items:
            return jsonify({"error": "No enabled items in test plan"}), 400

        if plan['is_template']:
            plan_id = _copy_plan(cursor, plan, g.active_engagement_id, plan['name'])
            cursor.execute("""
                SELECT id FROM test_plan_items WHERE test_plan_id = ? AND enabled = 1
                ORDER BY sort_order
            """, (plan_id,))
            items = cursor.fetchall()

        # Create execution records
        created = 0
        for (item_id,) in items:
            cursor.execute("""
                INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, host_id, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (g.active_engagement_id, plan_id, item_id, host_id))
            created += 1

        g.db.commit()

        return jsonify({
            "message": f"Created {created} execution records",
            "count": created,
            "plan_id": plan_id,
            "copied_from_template": plan['is_template']
        }), 201

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/executions/<int:execution_id>', methods=['GET'])
@require_auth
@require_active_engagement
def get_execution(execution_id):
    """Get a single execution record with full details."""
    try:
        cursor = g.db.cursor()

        cursor.execute("""
            SELECT te.*,
                   tp.name as plan_name,
                   tpi.atomic_id,
                   a.technique_id as technique_id,
                   a.technique_name,
                   COALESCE(a.atomic_test_name, tpi.custom_name) as atomic_test_name,
                   a.executor_command, a.description as atomic_description,
                   tpi.custom_name, tpi.custom_command,
                   h.ip as host_ip, h.hostname as host_hostname,
                   tpi.sort_order as item_sort_order, a.tactic as tactic,
                   ev.title as evidence_title
            FROM test_executions te
            JOIN test_plans tp ON te.test_plan_id = tp.id
            JOIN test_plan_items tpi ON te.test_plan_item_id = tpi.id
            LEFT JOIN atomics a ON tpi.atomic_id = a.id
            LEFT JOIN hosts h ON te.host_id = h.id
            LEFT JOIN evidence ev ON te.evidence_id = ev.id
            WHERE te.id = ? AND te.engagement_id = ?
        """, (execution_id, g.active_engagement_id))

        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Execution not found"}), 404

        columns = [desc[0] for desc in cursor.description]
        execution = dict(zip(columns, row))

        return jsonify(execution), 200

    except Exception as e:
        return internal_error(e)


@testplans_bp.route('/executions/<int:execution_id>', methods=['PUT'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
def update_execution(execution_id):
    """
    Update an execution record.
    Request body:
        - status: pending, in_progress, completed, failed, skipped
        - execution_output: Command output/result
        - execution_notes: User notes
        - outcome: prevented, alerted, logged, not_detected, or null
                   (not evaluated)
        - detected_by: control/source that detected it (free text)
    """
    try:
        data = request.get_json() or {}

        if 'status' in data and data['status'] not in EXECUTION_STATUSES:
            return jsonify({"error": f"status must be one of: {', '.join(EXECUTION_STATUSES)}"}), 400
        if 'outcome' in data:
            if data['outcome'] in ('', None):
                data['outcome'] = None
            elif data['outcome'] not in EXECUTION_OUTCOMES:
                return jsonify({"error": f"outcome must be one of: {', '.join(EXECUTION_OUTCOMES)}, or null"}), 400

        cursor = g.db.cursor()

        # Verify execution exists and belongs to engagement
        cursor.execute("""
            SELECT id, status FROM test_executions WHERE id = ? AND engagement_id = ?
        """, (execution_id, g.active_engagement_id))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Execution not found"}), 404

        current_status = row[1]
        new_status = data.get('status', current_status)

        # Set timestamps based on status
        started_at = None
        completed_at = None

        if new_status == 'in_progress' and current_status == 'pending':
            started_at = 'CURRENT_TIMESTAMP'

        if new_status in ['completed', 'failed', 'skipped'] and current_status in ['pending', 'in_progress']:
            completed_at = 'CURRENT_TIMESTAMP'

        # Build update query
        updates = []
        params = []

        if 'status' in data:
            updates.append("status = ?")
            params.append(data['status'])

        if 'execution_output' in data:
            updates.append("execution_output = ?")
            params.append(data['execution_output'])

        if 'execution_notes' in data:
            updates.append("execution_notes = ?")
            params.append(data['execution_notes'])

        if 'outcome' in data:
            updates.append("outcome = ?")
            params.append(data['outcome'])

        if 'detected_by' in data:
            updates.append("detected_by = ?")
            params.append((data['detected_by'] or '').strip() or None)

        if started_at:
            updates.append("execution_started_at = CURRENT_TIMESTAMP")

        if completed_at:
            updates.append("execution_completed_at = CURRENT_TIMESTAMP")

        updates.append("updated_at = CURRENT_TIMESTAMP")

        if updates:
            params.append(execution_id)
            cursor.execute(f"""
                UPDATE test_executions SET {', '.join(updates)} WHERE id = ?
            """, params)
            g.db.commit()

        return jsonify({"message": "Execution updated"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


def _match_log_results(cursor, plan_id, results):
    """
    Map parsed session-log results onto this plan's items.

    Order of preference:
      1. [item=N] tag naming an item of this plan
      2. [item=N] naming an item of another accessible plan (e.g. the script
         was generated from the template this plan was copied from): same
         atomic test, or same custom test name
      3. technique + test name, for logs from scripts without tags
    Ambiguous matches (several candidate items) are left unmatched.
    """
    cursor.execute("""
        SELECT tpi.id, tpi.atomic_id, tpi.custom_name, a.technique_id,
               COALESCE(a.atomic_test_name, tpi.custom_name) AS test_name
        FROM test_plan_items tpi
        LEFT JOIN atomics a ON a.id = tpi.atomic_id
        WHERE tpi.test_plan_id = ?
    """, (plan_id,))
    items = [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
    by_id = {item['id']: item for item in items}

    def unique(candidates):
        return (candidates[0]['id'], None) if len(candidates) == 1 else \
            (None, 'ambiguous' if candidates else None)

    matches = []
    for result in results:
        item_id, how, reason = None, None, None
        tag = result.get('item_id')

        if tag in by_id:
            item_id, how = tag, 'item'
        elif tag:
            cursor.execute("""
                SELECT tpi.atomic_id, tpi.custom_name
                FROM test_plan_items tpi
                JOIN test_plans tp ON tp.id = tpi.test_plan_id
                WHERE tpi.id = ? AND (tp.engagement_id IS NULL OR tp.engagement_id = ?)
            """, (tag, g.active_engagement_id))
            source = cursor.fetchone()
            if source:
                atomic_id, custom_name = source[0], source[1]
                candidates = [i for i in items if
                              (atomic_id is not None and i['atomic_id'] == atomic_id) or
                              (atomic_id is None and custom_name and i['custom_name'] == custom_name)]
                item_id, reason = unique(candidates)
                how = 'source' if item_id else None

        if item_id is None:
            name = (result.get('test_name') or '').strip().lower()
            technique = (result.get('technique_id') or '').strip().lower()
            if name:
                candidates = [i for i in items
                              if (i['test_name'] or '').strip().lower() == name
                              and (not technique or (i['technique_id'] or '').lower() == technique)]
                item_id, name_reason = unique(candidates)
                how = 'name' if item_id else None
                reason = reason or name_reason

        matches.append((item_id, how, None if item_id else (reason or 'not_in_plan')))
    return matches


@testplans_bp.route('/executions/import-log', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
def import_session_log():
    """
    Import a session log written by a PTVault-generated script.
    multipart/form-data:
        - file:    the log (tee / script / Tee-Object / Start-Transcript output)
        - plan_id: engagement plan the script was generated from (or a copy of)
        - host_id: host the script ran on; empty = no specific host
        - apply:   'true' to write changes; otherwise returns a preview only
    Updates run status, output and timestamps. Outcomes (detection) are never
    set from a log: only the defenders' side can tell you those.
    """
    from utils.session_log_parser import parse_session_log, decode_log, MAX_LOG_BYTES

    try:
        upload = request.files.get('file')
        if not upload:
            return jsonify({"error": "Choose a log file to import"}), 400

        raw = upload.read(MAX_LOG_BYTES + 1)
        if len(raw) > MAX_LOG_BYTES:
            return jsonify({"error": "Log file is larger than 10 MB"}), 413

        plan_id = request.form.get('plan_id', type=int)
        host_raw = (request.form.get('host_id') or '').strip()
        host_id = int(host_raw) if host_raw.isdigit() else None
        apply_changes = request.form.get('apply') == 'true'

        cursor = g.db.cursor()
        plan = _get_accessible_plan(cursor, plan_id) if plan_id else None
        if not plan:
            return jsonify({"error": "Test plan not found"}), 404
        if plan['is_template']:
            return jsonify({"error": "Import results into an engagement plan, not a template"}), 400

        if host_id:
            cursor.execute(
                "SELECT out_of_scope FROM hosts WHERE id = ? AND engagement_id = ?",
                (host_id, g.active_engagement_id)
            )
            host_row = cursor.fetchone()
            if not host_row:
                return jsonify({"error": "Host not found in the active engagement"}), 400
            if host_row[0]:
                return jsonify({"error": "Host is marked out of scope"}), 400

        results = parse_session_log(decode_log(raw))
        if not results:
            return jsonify({"error": "No PTVault test results found in this file. "
                                     "Import the log captured while running a PTVault-generated script."}), 400

        matches = _match_log_results(cursor, plan_id, results)

        cursor.execute("""
            SELECT id, test_plan_item_id, status, execution_output
            FROM test_executions
            WHERE engagement_id = ? AND test_plan_id = ? AND host_id IS ?
        """, (g.active_engagement_id, plan_id, host_id))
        existing = {row[1]: {'id': row[0], 'status': row[2], 'output': row[3]} for row in cursor.fetchall()}

        rows = []
        for result, (item_id, how, reason) in zip(results, matches):
            rows.append({
                'test_number': result['test_number'],
                'technique_id': result['technique_id'],
                'test_name': result['test_name'],
                'status': result['status'],
                'exit_code': result['exit_code'],
                'duration_seconds': result['duration_seconds'],
                'has_output': bool(result['output']),
                'item_id': item_id,
                'matched_by': how,
                'unmatched_reason': reason,
                'execution_id': existing[item_id]['id'] if item_id in existing else None,
            })

        summary = {
            'total': len(rows),
            'matched': sum(1 for r in rows if r['item_id']),
            'unmatched': sum(1 for r in rows if not r['item_id']),
            'new_executions': sum(1 for r in rows if r['item_id'] and not r['execution_id']),
        }

        if not apply_changes:
            return jsonify({'preview': True, 'summary': summary, 'results': rows}), 200

        updated = created = 0
        for result, row in zip(results, rows):
            item_id = row['item_id']
            if not item_id:
                continue
            current = existing.get(item_id)
            if current is None:
                cursor.execute("""
                    INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, host_id, status)
                    VALUES (?, ?, ?, ?, 'pending')
                """, (g.active_engagement_id, plan_id, item_id, host_id))
                current = existing[item_id] = {'id': cursor.lastrowid, 'status': 'pending', 'output': None}
                created += 1

            # A log that stops mid-test must not downgrade a finished result
            new_status = result['status']
            if new_status == 'in_progress' and current['status'] != 'pending':
                new_status = current['status']

            log_output = result['output'] or ''
            old_output = current['output'] or ''
            if not log_output or log_output in old_output:
                new_output = old_output
            elif not old_output.strip():
                new_output = log_output
            else:
                new_output = f"{old_output.rstrip()}\n\n--- Imported from session log ---\n{log_output}"

            cursor.execute("""
                UPDATE test_executions
                SET status = ?,
                    execution_output = ?,
                    execution_started_at = COALESCE(?, execution_started_at),
                    execution_completed_at = COALESCE(?, execution_completed_at),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_status, new_output or None, result['started_at'],
                  result['completed_at'] if new_status in ('completed', 'failed', 'skipped') else None,
                  current['id']))
            current.update(status=new_status, output=new_output)
            updated += 1

        g.db.commit()
        return jsonify({
            'preview': False,
            'summary': {**summary, 'updated': updated, 'created': created},
            'results': rows,
        }), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/executions/<int:execution_id>/link-evidence', methods=['POST'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
def link_evidence(execution_id):
    """
    Link evidence to an execution record.
    Request body:
        - evidence_id: ID of the evidence to link
    """
    try:
        data = request.get_json()
        evidence_id = data.get('evidence_id')

        if not evidence_id:
            return jsonify({"error": "evidence_id is required"}), 400

        cursor = g.db.cursor()

        # Verify execution exists
        cursor.execute("""
            SELECT id FROM test_executions WHERE id = ? AND engagement_id = ?
        """, (execution_id, g.active_engagement_id))
        if not cursor.fetchone():
            return jsonify({"error": "Execution not found"}), 404

        # Verify evidence exists
        cursor.execute("""
            SELECT id FROM evidence WHERE id = ? AND engagement_id = ?
        """, (evidence_id, g.active_engagement_id))
        if not cursor.fetchone():
            return jsonify({"error": "Evidence not found"}), 404

        cursor.execute("""
            UPDATE test_executions SET evidence_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (evidence_id, execution_id))
        g.db.commit()

        return jsonify({"message": "Evidence linked"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/executions/<int:execution_id>', methods=['DELETE'])
@require_auth
@require_engagement_access('editor')
@require_active_engagement
def delete_execution(execution_id):
    """Delete an execution record."""
    try:
        cursor = g.db.cursor()
        cursor.execute("""
            DELETE FROM test_executions WHERE id = ? AND engagement_id = ?
        """, (execution_id, g.active_engagement_id))
        g.db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "Execution not found"}), 404

        return jsonify({"message": "Execution deleted"}), 200

    except Exception as e:
        g.db.rollback()
        return internal_error(e)


@testplans_bp.route('/executions/plan/<int:plan_id>/progress', methods=['GET'])
@require_auth
@require_active_engagement
def get_plan_progress(plan_id):
    """Get execution progress for a test plan in the current engagement."""
    try:
        cursor = g.db.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
            FROM test_executions
            WHERE test_plan_id = ? AND engagement_id = ?
        """, (plan_id, g.active_engagement_id))

        row = cursor.fetchone()

        return jsonify({
            "total": row[0] or 0,
            "pending": row[1] or 0,
            "in_progress": row[2] or 0,
            "completed": row[3] or 0,
            "failed": row[4] or 0,
            "skipped": row[5] or 0
        }), 200

    except Exception as e:
        return internal_error(e)

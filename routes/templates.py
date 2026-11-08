"""Template management routes for PTVault."""

from flask import Blueprint, jsonify, g, session, Response
from middleware.auth import require_auth
from utils.error_handler import handle_errors
from jinja2.sandbox import SandboxedEnvironment
from datetime import datetime, timezone
from routes.engagements import get_engagement_export_data
from config import BASE_DIR
import os
import re

from utils.security_headers import attachment_disposition

templates_bp = Blueprint('templates', __name__, url_prefix='/api')

# Template directory — use BASE_DIR for PyInstaller compatibility
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates', 'reports')
_TEMPLATE_NAME = re.compile(r'[A-Za-z0-9_-]{1,64}')
# Templates are server files today; a sandbox keeps a template from reaching
# Python internals if templates ever become user-editable (L-12).
_JINJA = SandboxedEnvironment(autoescape=False)


def _template_path(template_name):
    """Path of a report template, or None for a name that is not a plain identifier."""
    if not _TEMPLATE_NAME.fullmatch(template_name or ''):
        return None
    return os.path.join(TEMPLATE_DIR, f'{template_name}.md')


@templates_bp.route('/templates', methods=['GET'])
@require_auth
@handle_errors
def list_templates():
    """
    List all available report templates.
    Returns array of template names and filenames.
    """
    templates = []
    template_path = TEMPLATE_DIR

    if not os.path.exists(template_path):
        return jsonify({'templates': []})

    for filename in os.listdir(template_path):
        if filename.endswith('.md'):
            templates.append({
                'name': filename.replace('.md', ''),
                'filename': filename
            })

    return jsonify({'templates': templates})


@templates_bp.route('/templates/<string:template_name>', methods=['GET'])
@require_auth
@handle_errors
def get_template(template_name):
    """
    Get the raw content of a template file.
    Returns the template as Markdown text.
    """
    template_path = _template_path(template_name)

    if not template_path or not os.path.exists(template_path):
        return jsonify({'error': 'Template not found'}), 404

    with open(template_path, 'r') as f:
        content = f.read()

    response = Response(content, mimetype='text/markdown')
    return response


@templates_bp.route('/engagements/<int:engagement_id>/export/template/<string:template_name>', methods=['GET'])
@require_auth
@handle_errors
def export_with_template(engagement_id, template_name):
    """
    Export engagement data using a specific template.
    Renders the template with engagement data using Jinja2.
    """
    # Verify engagement belongs to active engagement (security)
    active_id = session.get('active_engagement_id')
    if engagement_id != active_id:
        return jsonify({'error': 'Unauthorized - engagement must be active'}), 403

    # Load template
    template_path = _template_path(template_name)

    if not template_path or not os.path.exists(template_path):
        return jsonify({'error': 'Template not found'}), 404

    with open(template_path, 'r') as f:
        template_content = f.read()

    try:
        # Load engagement data
        data = get_engagement_export_data(engagement_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

    # Add convenience variables for template
    context = {
        'engagement': data['engagement'],
        'evidence': data['evidence'],
        'statistics': data['statistics'],
        'critical_findings': [e for e in data['evidence'] if e.get('severity_level') == 'critical'],
        'high_findings': [e for e in data['evidence'] if e.get('severity_level') == 'high'],
        'medium_findings': [e for e in data['evidence'] if e.get('severity_level') == 'medium'],
        'low_findings': [e for e in data['evidence'] if e.get('severity_level') == 'low'],
        'export_date': datetime.now(timezone.utc).strftime('%Y-%m-%d')
    }

    # Render with Jinja2
    rendered = _JINJA.from_string(template_content).render(**context)

    response = Response(rendered, mimetype='text/markdown')
    response.headers['Content-Disposition'] = attachment_disposition(f'report-{template_name}-{engagement_id}.md')
    return response

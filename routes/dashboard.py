"""Dashboard metrics endpoint — read-only aggregate of the active engagement."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify

from middleware.auth import require_auth, require_engagement_access
from models.dao.dashboard_dao import DashboardDAO
from utils.error_handler import handle_errors

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/metrics', methods=['GET'])
@require_auth
@require_engagement_access('viewer')
@handle_errors
def get_metrics():
    """Return all dashboard metrics for the active engagement in one envelope."""
    engagement_id = g.active_engagement_id
    dao = DashboardDAO()

    payload = {
        'engagement_id': engagement_id,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'kpis': dao.get_kpis(engagement_id),
        'severity': dao.get_severity_breakdown(engagement_id),
        'scan_vulnerabilities': dao.get_scan_vulnerabilities(engagement_id),
        'top_ports': dao.get_top_ports(engagement_id, limit=15),
        'host_status': dao.get_host_status(engagement_id),
        'top_services': dao.get_top_services(engagement_id, limit=10),
        'findings_over_time': dao.get_findings_over_time(engagement_id),
        'color_categories': dao.get_color_categories(engagement_id),
        'test_executions': dao.get_test_execution_summary(engagement_id),
    }
    return jsonify(payload), 200

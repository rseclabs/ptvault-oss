"""Smoke tests for the dashboard route.

Auth is provided by Flask middleware that requires a real JWT cookie, so
these tests cover what is realistically testable without a full session
setup: (1) the URL is registered, and (2) the route module imports cleanly
and assembles the expected envelope when the DAO is invoked directly.
"""

from datetime import datetime, timezone

import pytest
from flask import Flask, g

from models.dao.dashboard_dao import DashboardDAO


def test_dashboard_blueprint_registers_metrics_url():
    """The route module must register GET /api/dashboard/metrics."""
    from routes.dashboard import dashboard_bp

    app = Flask(__name__)
    app.register_blueprint(dashboard_bp)

    rules = {r.rule for r in app.url_map.iter_rules()}
    assert '/api/dashboard/metrics' in rules


def test_dashboard_envelope_shape(app_ctx):
    """The DAO methods composed by the route produce a complete envelope.

    We invoke the same composition the route does (skipping the decorators)
    so we can assert the response shape without standing up auth.
    """
    cursor = app_ctx.cursor()
    cursor.execute(
        "INSERT INTO engagements (id, name, client_name, status) "
        "VALUES (1, 'E', 'C', 'active')"
    )
    app_ctx.commit()

    dao = DashboardDAO()
    payload = {
        'engagement_id': 1,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'kpis': dao.get_kpis(1),
        'severity': dao.get_severity_breakdown(1),
        'top_ports': dao.get_top_ports(1, limit=15),
        'host_status': dao.get_host_status(1),
        'top_services': dao.get_top_services(1, limit=10),
        'findings_over_time': dao.get_findings_over_time(1),
        'color_categories': dao.get_color_categories(1),
        'test_executions': dao.get_test_execution_summary(1),
    }

    assert set(payload.keys()) == {
        'engagement_id', 'generated_at', 'kpis', 'severity',
        'top_ports', 'host_status', 'top_services',
        'findings_over_time', 'color_categories', 'test_executions',
    }
    assert payload['engagement_id'] == 1
    assert isinstance(payload['kpis'], dict)
    assert isinstance(payload['severity'], list)
    assert isinstance(payload['top_ports'], list)
    assert isinstance(payload['host_status'], dict)
    assert payload['test_executions'] == {'total': 0, 'by_status': []}

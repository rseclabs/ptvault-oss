"""H-5: reporting routes act only on engagements the caller can access.

Engagement ids in query strings and bodies are checked, reports are created
only in the verified active engagement, and a report item cannot pull in a
finding from another engagement.
"""

import json

import pytest

from tests.conftest import ENGAGEMENT_A, ENGAGEMENT_B

SECRET = 'A-only SQL injection in billing'


@pytest.fixture
def seeded(live_app):
    conn = live_app.db()
    finding_a = conn.execute(
        "INSERT INTO engagement_findings (engagement_id, title, criticality, finding_content) "
        "VALUES (?, ?, 'critical', 'details')", (ENGAGEMENT_A, SECRET)).lastrowid
    conn.execute("INSERT INTO reports (engagement_id, name, structure) VALUES (?, 'A report', '[]')",
                 (ENGAGEMENT_A,))
    conn.execute("INSERT INTO report_templates (id, name, structure) VALUES (1, 'Template', '[]')")
    # A report in B whose item points at A's finding.
    item = [{'id': 'x', 'type': 'engagement_finding', 'source_id': finding_a, 'position': 0}]
    report_b = conn.execute("INSERT INTO reports (engagement_id, name, structure) VALUES (?, 'B report', ?)",
                            (ENGAGEMENT_B, json.dumps(item))).lastrowid
    conn.commit()
    conn.close()
    live_app.finding_a, live_app.report_b = finding_a, report_b
    return live_app


def _report_count(live, engagement_id):
    conn = live.db()
    count = conn.execute('SELECT COUNT(*) FROM reports WHERE engagement_id = ?', (engagement_id,)).fetchone()[0]
    conn.close()
    return count


def test_list_reports_of_another_engagement_is_refused(seeded):
    outsider = seeded.client_for('outsider', active_engagement=ENGAGEMENT_B)
    assert outsider.get(f'/api/reporting/reports?engagement_id={ENGAGEMENT_A}').status_code == 404

    viewer = seeded.client_for('viewer', active_engagement=ENGAGEMENT_A)
    resp = viewer.get(f'/api/reporting/reports?engagement_id={ENGAGEMENT_A}')
    assert resp.status_code == 200
    assert [r['name'] for r in resp.get_json()] == ['A report']


def test_list_reports_defaults_to_active_engagement(seeded):
    resp = seeded.client_for('editor', active_engagement=ENGAGEMENT_A).get('/api/reporting/reports')
    assert resp.status_code == 200
    assert [r['name'] for r in resp.get_json()] == ['A report']


def test_report_cannot_be_created_in_another_engagement(seeded):
    client = seeded.client_for('outsider', active_engagement=ENGAGEMENT_B)
    resp = client.post('/api/reporting/reports', json={'engagement_id': ENGAGEMENT_A, 'name': 'planted'})
    assert resp.status_code == 400
    assert _report_count(seeded, ENGAGEMENT_A) == 1


def test_report_is_created_in_active_engagement(seeded):
    client = seeded.client_for('outsider', active_engagement=ENGAGEMENT_B)
    resp = client.post('/api/reporting/reports', json={'name': 'mine'})
    assert resp.status_code == 201
    assert resp.get_json()['engagement_id'] == ENGAGEMENT_B


def test_template_cannot_be_applied_to_another_engagement(seeded):
    client = seeded.client_for('outsider', active_engagement=ENGAGEMENT_B)
    resp = client.post('/api/reporting/templates/1/apply', json={'engagement_id': ENGAGEMENT_A})
    assert resp.status_code == 400
    assert _report_count(seeded, ENGAGEMENT_A) == 1


def test_template_preview_of_another_engagement_is_refused(seeded):
    client = seeded.client_for('outsider', active_engagement=ENGAGEMENT_B)
    resp = client.get(f'/api/reporting/templates/1/preview?engagement_id={ENGAGEMENT_A}')
    assert resp.status_code == 404
    assert resp.get_json()['error'] == 'engagement not found'
    assert SECRET.encode() not in resp.data


def test_compare_requires_access_to_every_engagement(seeded):
    body = {'engagement_ids': [ENGAGEMENT_A, ENGAGEMENT_B]}
    outsider = seeded.client_for('outsider', active_engagement=ENGAGEMENT_B)
    resp = outsider.post('/api/reporting/compare', json=body)
    assert resp.status_code == 404
    assert b'Engagement A' not in resp.data
    assert seeded.client_for('admin').post('/api/reporting/compare', json=body).status_code == 200


@pytest.mark.parametrize('path', ['/api/reporting/reports/{id}', '/api/reporting/reports/{id}/export?format=markdown'])
def test_report_item_cannot_pull_finding_from_another_engagement(seeded, path):
    client = seeded.client_for('outsider', active_engagement=ENGAGEMENT_B)
    resp = client.get(path.format(id=seeded.report_b))
    assert resp.status_code == 200
    assert SECRET.encode() not in resp.data

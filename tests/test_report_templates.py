"""Tests for report template functionality.

Uses conftest fixtures (app_ctx + sample_engagement) so DAOs run with the
real Flask `g.db` and the production schema. ReportAutoPopulator and
TemplateRenderer take the connection directly, so they're constructed with
the underlying conn yielded by app_ctx.
"""

import json

import pytest

from models.dao.template_dao import TemplateDAO
from utils.report_auto_populator import ReportAutoPopulator
from utils.template_renderer import TemplateRenderer


def test_create_template(app_ctx):
    dao = TemplateDAO()
    structure = [
        {'type': 'auto', 'section_type': 'executive_summary', 'title': 'Executive Summary'},
        {'type': 'custom', 'title': 'Introduction', 'content': 'This is a test report for {{CLIENT_NAME}}'},
    ]

    template_id = dao.create({
        'name': 'Test Template',
        'description': 'A test template',
        'category': 'custom',
        'structure': json.dumps(structure),
        'placeholders': json.dumps({'CLIENT_NAME': 'Client name'}),
        'is_default': 0,
        'is_public': 1,
        'created_by': 1,
    })

    assert template_id > 0
    template = dao.find_by_id(template_id)
    assert template['name'] == 'Test Template'
    assert template['category'] == 'custom'
    assert template['is_public'] == 1


def test_find_by_category(app_ctx):
    dao = TemplateDAO()
    for category in ['executive', 'technical', 'custom']:
        dao.create({
            'name': f'{category.title()} Template',
            'category': category,
            'structure': json.dumps([]),
            'is_public': 1,
        })

    executive_templates = dao.find_by_category('executive')
    assert len(executive_templates) >= 1
    assert all(t['category'] == 'executive' for t in executive_templates)


def test_duplicate_template(app_ctx):
    dao = TemplateDAO()
    original_id = dao.create({
        'name': 'Original Template',
        'description': 'Original description',
        'category': 'custom',
        'structure': json.dumps([{'type': 'custom', 'content': 'Test'}]),
        'is_public': 1,
    })

    new_id = dao.duplicate_template(original_id, 'Duplicated Template')

    original = dao.find_by_id(original_id)
    duplicate = dao.find_by_id(new_id)

    assert duplicate['name'] == 'Duplicated Template'
    assert duplicate['description'] == original['description']
    assert duplicate['structure'] == original['structure']
    assert duplicate['is_default'] == 0


def test_apply_template_to_engagement(app_ctx, sample_engagement):
    dao = TemplateDAO()
    structure = [
        {'type': 'auto', 'section_type': 'executive_summary'},
        {'type': 'auto', 'section_type': 'findings_list'},
    ]
    template_id = dao.create({
        'name': 'Test Report Template',
        'structure': json.dumps(structure),
        'is_public': 1,
    })

    report_id = dao.apply_to_engagement(template_id, sample_engagement, 'Test Report')
    assert report_id > 0

    cursor = app_ctx.cursor()
    cursor.execute('SELECT structure FROM reports WHERE id = ?', (report_id,))
    row = cursor.fetchone()
    assert row is not None

    # apply_to_engagement stores rendered workspace items as JSON in
    # reports.structure (not as rows in report_sections). Auto sections
    # without a title produce one text block each, so 2 -> 2 items.
    items = json.loads(row['structure'])
    assert len(items) == 2
    assert all(item.get('type') == 'format_tool' for item in items)
    assert all(item.get('format_tool_id') == 'textblock' for item in items)


def test_auto_populator_executive_summary(app_ctx, sample_engagement):
    populator = ReportAutoPopulator(app_ctx, sample_engagement)
    summary = populator.populate_executive_summary()

    assert 'Executive Summary' in summary
    assert 'ACME Corp' in summary
    assert 'critical' in summary.lower()


def test_auto_populator_findings_list(app_ctx, sample_engagement):
    populator = ReportAutoPopulator(app_ctx, sample_engagement)

    findings = populator.populate_findings_list()
    assert 'SQL Injection' in findings
    assert 'Weak Password Policy' in findings

    critical_findings = populator.populate_findings_list(severity='critical')
    assert 'SQL Injection' in critical_findings
    assert 'Weak Password Policy' not in critical_findings

    limited_findings = populator.populate_findings_list(limit=1)
    assert 'SQL Injection' in limited_findings


def test_auto_populator_host_summary(app_ctx, sample_engagement):
    populator = ReportAutoPopulator(app_ctx, sample_engagement)
    summary = populator.populate_host_summary()

    assert 'Host Summary' in summary
    assert '192.168.1.10' in summary
    assert 'server1' in summary


def test_auto_populator_recommendations(app_ctx, sample_engagement):
    populator = ReportAutoPopulator(app_ctx, sample_engagement)
    recommendations = populator.populate_recommendations()

    assert 'Recommendations' in recommendations
    assert 'parameterized queries' in recommendations


def test_placeholder_replacement(app_ctx, sample_engagement):
    populator = ReportAutoPopulator(app_ctx, sample_engagement)

    # conftest sample_engagement seeds 2 hosts and 2 findings
    assert populator.get_placeholder_value('ENGAGEMENT_NAME') == 'Test Engagement'
    assert populator.get_placeholder_value('CLIENT_NAME') == 'ACME Corp'
    assert populator.get_placeholder_value('START_DATE') == '2024-01-01'
    assert populator.get_placeholder_value('END_DATE') == '2024-01-15'
    assert populator.get_placeholder_value('HOST_COUNT') == '2'
    assert populator.get_placeholder_value('FINDING_COUNT') == '2'


def test_template_renderer(app_ctx, sample_engagement):
    structure = json.dumps([
        {'type': 'custom', 'title': 'Report for {{CLIENT_NAME}}', 'content': 'Assessment of {{HOST_COUNT}} systems'},
        {'type': 'auto', 'section_type': 'executive_summary'},
    ])

    renderer = TemplateRenderer(app_ctx, sample_engagement)
    sections = renderer.render_template(structure)

    assert len(sections) == 2
    assert sections[0]['title'] == 'Report for ACME Corp'
    assert '2 systems' in sections[0]['content']
    assert sections[1]['type'] == 'auto'
    assert 'ACME Corp' in sections[1]['content']


def test_template_with_usage_count(app_ctx, sample_engagement):
    dao = TemplateDAO()
    template_id = dao.create({
        'name': 'Usage Test Template',
        'structure': json.dumps([]),
        'is_public': 1,
    })

    for i in range(3):
        dao.apply_to_engagement(template_id, sample_engagement, f'Report {i}')

    templates = dao.get_with_usage_count()
    usage_template = next((t for t in templates if t['id'] == template_id), None)
    assert usage_template is not None
    assert usage_template['usage_count'] == 3


def test_comparison_metrics(app_ctx):
    cursor = app_ctx.cursor()

    engagement_ids = []
    for i in range(2):
        cursor.execute(
            'INSERT INTO engagements (name, client_name, start_date) VALUES (?, ?, ?)',
            (f'Engagement {i}', f'Client {i}', f'2024-0{i+1}-01'),
        )
        engagement_id = cursor.lastrowid
        engagement_ids.append(engagement_id)

        for severity in ['critical', 'high', 'medium']:
            cursor.execute(
                'INSERT INTO engagement_findings (engagement_id, title, criticality) VALUES (?, ?, ?)',
                (engagement_id, f'{severity.title()} Finding', severity),
            )

    app_ctx.commit()

    from routes.reporting import _calculate_comparison_metrics
    metrics = _calculate_comparison_metrics(engagement_ids, cursor)

    assert metrics['avg_findings_per_engagement'] == 3.0
    assert 'critical' in metrics['severity_distribution']
    assert metrics['severity_distribution']['critical'] == 2


def test_comparison_trends(app_ctx):
    cursor = app_ctx.cursor()

    engagement_ids = []
    for i in range(3):
        cursor.execute(
            'INSERT INTO engagements (name, client_name, start_date) VALUES (?, ?, ?)',
            (f'Engagement {i}', 'Client', f'2024-0{i+1}-01'),
        )
        eid = cursor.lastrowid
        engagement_ids.append(eid)
        for j in range(i + 1):
            cursor.execute(
                'INSERT INTO engagement_findings (engagement_id, title, criticality) VALUES (?, ?, ?)',
                (eid, f'Finding {j}', 'high'),
            )

    app_ctx.commit()

    from routes.reporting import _calculate_trends
    trends = _calculate_trends(engagement_ids, cursor)

    assert len(trends['findings_over_time']) == 3
    assert trends['findings_over_time'][0]['finding_count'] == 1
    assert trends['findings_over_time'][1]['finding_count'] == 2
    assert trends['findings_over_time'][2]['finding_count'] == 3


@pytest.mark.parametrize('severity,expected_count', [
    ('critical', 1),
    ('medium', 1),
    (None, 2),
])
def test_findings_list_filtering(app_ctx, sample_engagement, severity, expected_count):
    populator = ReportAutoPopulator(app_ctx, sample_engagement)
    findings = populator.populate_findings_list(severity=severity)
    # Each finding becomes "## N. Title". Sub-sections are "### " so use a
    # newline-anchored match to avoid counting them.
    assert findings.count('\n## ') == expected_count

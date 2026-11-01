"""Tests for DashboardDAO — per-engagement metric aggregation."""

from models.dao.dashboard_dao import DashboardDAO


def _seed_engagement(cursor, eid=1, end_date='2026-12-31'):
    cursor.execute(
        "INSERT INTO engagements (id, name, client_name, start_date, end_date, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (eid, 'Test Eng', 'ACME', '2026-01-01', end_date, 'active'),
    )


def _seed_host(cursor, eid, ip, **flags):
    cols = ['engagement_id', 'ip'] + list(flags.keys())
    vals = [eid, ip] + list(flags.values())
    placeholders = ','.join(['?'] * len(vals))
    cursor.execute(
        f"INSERT INTO hosts ({','.join(cols)}) VALUES ({placeholders})",
        vals,
    )
    return cursor.lastrowid


def test_get_kpis_counts_hosts_ports_findings_creds(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    h1 = _seed_host(cursor, 1, '10.0.0.1', rooted=1)
    h2 = _seed_host(cursor, 1, '10.0.0.2', shell=1)
    _seed_host(cursor, 1, '10.0.0.3')
    cursor.execute("INSERT INTO host_ports (host_id, port, state) VALUES (?, 80, 'open')", (h1,))
    cursor.execute("INSERT INTO host_ports (host_id, port, state) VALUES (?, 443, 'open')", (h1,))
    cursor.execute("INSERT INTO host_ports (host_id, port, state) VALUES (?, 22, 'closed')", (h2,))
    cursor.execute(
        "INSERT INTO host_credentials (host_id, username, password) VALUES (?, 'admin', 'pw')",
        (h1,),
    )
    cursor.execute(
        "INSERT INTO engagement_findings (engagement_id, title, criticality) "
        "VALUES (1, 'XSS', 'high')"
    )
    app_ctx.commit()

    dao = DashboardDAO()
    kpis = dao.get_kpis(1)

    assert kpis['hosts'] == 3
    assert kpis['open_ports'] == 2
    assert kpis['findings'] == 1
    assert kpis['credentials'] == 1
    assert kpis['compromised_hosts'] == 2  # rooted OR shell
    assert isinstance(kpis['days_remaining'], int)


def test_get_kpis_returns_zero_for_empty_engagement(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    app_ctx.commit()

    dao = DashboardDAO()
    kpis = dao.get_kpis(1)

    assert kpis == {
        'hosts': 0, 'open_ports': 0, 'findings': 0,
        'credentials': 0, 'compromised_hosts': 0,
        'days_remaining': kpis['days_remaining'],  # date-dependent
    }


def test_get_kpis_days_remaining_handles_missing_end_date(app_ctx):
    cursor = app_ctx.cursor()
    cursor.execute(
        "INSERT INTO engagements (id, name, client_name, start_date, status) "
        "VALUES (1, 'NoEnd', 'C', '2026-01-01', 'active')"
    )
    app_ctx.commit()

    dao = DashboardDAO()
    kpis = dao.get_kpis(1)
    assert kpis['days_remaining'] is None


def test_severity_breakdown_groups_by_criticality(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    for crit in ['critical', 'critical', 'high', 'medium', 'medium', 'medium', 'low']:
        cursor.execute(
            "INSERT INTO engagement_findings (engagement_id, title, criticality) "
            "VALUES (1, 'F', ?)",
            (crit,),
        )
    cursor.execute(
        "INSERT INTO engagement_findings (engagement_id, title, criticality) "
        "VALUES (1, 'F', NULL)"
    )
    app_ctx.commit()

    dao = DashboardDAO()
    sev = dao.get_severity_breakdown(1)

    by = {row['label']: row['count'] for row in sev}
    assert by == {'critical': 2, 'high': 1, 'medium': 3, 'low': 1, 'info': 1}


def test_severity_breakdown_empty(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    app_ctx.commit()

    assert DashboardDAO().get_severity_breakdown(1) == []


def test_top_ports_orders_by_host_count_desc(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    h1 = _seed_host(cursor, 1, '10.0.0.1')
    h2 = _seed_host(cursor, 1, '10.0.0.2')
    h3 = _seed_host(cursor, 1, '10.0.0.3')
    # Port 80 on three hosts, port 22 on two, port 3306 on one
    for hid in (h1, h2, h3):
        cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                       "VALUES (?, 80, 'open', 'http')", (hid,))
    for hid in (h1, h2):
        cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                       "VALUES (?, 22, 'open', 'ssh')", (hid,))
    cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                   "VALUES (?, 3306, 'open', 'mysql')", (h1,))
    # Closed port should be excluded
    cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                   "VALUES (?, 8080, 'closed', 'http-alt')", (h1,))
    app_ctx.commit()

    rows = DashboardDAO().get_top_ports(1, limit=15)

    assert [r['port'] for r in rows] == [80, 22, 3306]
    assert rows[0] == {'port': 80, 'host_count': 3, 'service': 'http'}
    assert rows[1]['service'] == 'ssh'


def test_top_ports_respects_limit(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    h = _seed_host(cursor, 1, '10.0.0.1')
    for p in range(1, 21):
        cursor.execute("INSERT INTO host_ports (host_id, port, state) "
                       "VALUES (?, ?, 'open')", (h, p))
    app_ctx.commit()

    rows = DashboardDAO().get_top_ports(1, limit=5)
    assert len(rows) == 5


def test_host_status_categorizes_each_host_once(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    _seed_host(cursor, 1, '10.0.0.1', rooted=1, shell=1)         # rooted
    _seed_host(cursor, 1, '10.0.0.2', rooted=1)                   # rooted
    _seed_host(cursor, 1, '10.0.0.3', shell=1)                    # shell-only
    _seed_host(cursor, 1, '10.0.0.4', reviewed=1)                 # reviewed
    _seed_host(cursor, 1, '10.0.0.5', flagged=1)                  # flagged
    _seed_host(cursor, 1, '10.0.0.6', out_of_scope=1)             # OOS
    _seed_host(cursor, 1, '10.0.0.7')                             # untouched
    _seed_host(cursor, 1, '10.0.0.8')                             # untouched
    app_ctx.commit()

    status = DashboardDAO().get_host_status(1)

    assert status == {
        'rooted': 2, 'shell_only': 1, 'reviewed': 1, 'flagged': 1,
        'out_of_scope': 1, 'untouched': 2, 'total': 8,
    }


def test_host_status_empty(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    app_ctx.commit()
    assert DashboardDAO().get_host_status(1) == {
        'rooted': 0, 'shell_only': 0, 'reviewed': 0, 'flagged': 0,
        'out_of_scope': 0, 'untouched': 0, 'total': 0,
    }


def test_top_services_buckets_unknown_and_orders(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    h1 = _seed_host(cursor, 1, '10.0.0.1')
    h2 = _seed_host(cursor, 1, '10.0.0.2')
    h3 = _seed_host(cursor, 1, '10.0.0.3')
    for hid in (h1, h2, h3):
        cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                       "VALUES (?, 80, 'open', 'http')", (hid,))
    for hid in (h1, h2):
        cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                       "VALUES (?, 22, 'open', 'ssh')", (hid,))
    cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                   "VALUES (?, 12345, 'open', '')", (h1,))
    cursor.execute("INSERT INTO host_ports (host_id, port, state, service) "
                   "VALUES (?, 12346, 'open', NULL)", (h2,))
    app_ctx.commit()

    rows = DashboardDAO().get_top_services(1, limit=10)
    by_svc = {r['service']: r['host_count'] for r in rows}
    assert by_svc['http'] == 3
    assert by_svc['ssh'] == 2
    assert by_svc['(unknown)'] == 2
    # http should be first
    assert rows[0]['service'] == 'http'


def test_findings_over_time_returns_cumulative_series(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    cursor.execute(
        "INSERT INTO engagement_findings "
        "(engagement_id, title, criticality, created_at) "
        "VALUES (1, 'A', 'high', '2026-04-20 10:00:00')"
    )
    cursor.execute(
        "INSERT INTO engagement_findings "
        "(engagement_id, title, criticality, created_at) "
        "VALUES (1, 'B', 'medium', '2026-04-20 14:00:00')"
    )
    cursor.execute(
        "INSERT INTO engagement_findings "
        "(engagement_id, title, criticality, created_at) "
        "VALUES (1, 'C', 'low', '2026-04-22 09:00:00')"
    )
    app_ctx.commit()

    series = DashboardDAO().get_findings_over_time(1)
    assert series == [
        {'day': '2026-04-20', 'cumulative': 2},
        {'day': '2026-04-22', 'cumulative': 3},
    ]


def test_findings_over_time_empty(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    app_ctx.commit()
    assert DashboardDAO().get_findings_over_time(1) == []


def test_color_categories_groups_uncategorized_under_null(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    _seed_host(cursor, 1, '10.0.0.1', color_category='red')
    _seed_host(cursor, 1, '10.0.0.2', color_category='red')
    _seed_host(cursor, 1, '10.0.0.3', color_category='yellow')
    _seed_host(cursor, 1, '10.0.0.4')  # NULL
    _seed_host(cursor, 1, '10.0.0.5')  # NULL
    app_ctx.commit()

    rows = DashboardDAO().get_color_categories(1)
    by = {r['color']: r['count'] for r in rows}
    assert by == {'red': 2, 'yellow': 1, None: 2}


def test_test_execution_summary_groups_by_status(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    cursor.execute(
        "INSERT INTO test_plans (id, name) VALUES (1, 'Plan A')"
    )
    cursor.execute(
        "INSERT INTO test_plan_items (id, test_plan_id) VALUES (1, 1)"
    )
    for status in ['pending', 'pending', 'passed', 'failed']:
        cursor.execute(
            "INSERT INTO test_executions "
            "(engagement_id, test_plan_id, test_plan_item_id, status) "
            "VALUES (1, 1, 1, ?)",
            (status,),
        )
    app_ctx.commit()

    summary = DashboardDAO().get_test_execution_summary(1)
    assert summary['total'] == 4
    by = {r['status']: r['count'] for r in summary['by_status']}
    assert by == {'pending': 2, 'passed': 1, 'failed': 1}


def test_test_execution_summary_empty(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    app_ctx.commit()
    summary = DashboardDAO().get_test_execution_summary(1)
    assert summary == {'total': 0, 'by_status': []}


# --------------------------------------------------------------------------
# get_scan_vulnerabilities — walks evidence metadata for Nessus / Burp counts
# --------------------------------------------------------------------------

import json as _json


def _seed_evidence(cursor, eid, metadata):
    cursor.execute(
        "INSERT INTO evidence (engagement_id, evidence_type, title, metadata) "
        "VALUES (?, 'tool_output', 'Scan', ?)",
        (eid, _json.dumps(metadata)),
    )


def test_scan_vulnerabilities_empty_engagement(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    app_ctx.commit()
    assert DashboardDAO().get_scan_vulnerabilities(1) == {
        'critical': 0, 'high': 0, 'medium': 0, 'low': 0,
    }


def test_scan_vulnerabilities_counts_nessus_per_severity(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    _seed_evidence(cursor, 1, {
        'tool': 'nessus',
        'hosts': [
            {'ip': '10.0.0.1', 'vulnerabilities': [
                {'severity': 4}, {'severity': 4},
                {'severity': 3},
                {'severity': 2}, {'severity': 2}, {'severity': 2},
                {'severity': 1},
                {'severity': 0},  # ignored — informational
            ]},
            {'ip': '10.0.0.2', 'vulnerabilities': [
                {'severity': 4},
                {'severity': 3}, {'severity': 3},
            ]},
        ],
    })
    app_ctx.commit()

    counts = DashboardDAO().get_scan_vulnerabilities(1)
    assert counts == {'critical': 3, 'high': 3, 'medium': 3, 'low': 1}


def test_scan_vulnerabilities_sums_burp_summary(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    _seed_evidence(cursor, 1, {
        'tool': 'burp_suite',
        'summary': {
            'by_severity': {'Critical': 2, 'High': 5, 'Medium': 7, 'Low': 1, 'Info': 99},
        },
    })
    # A second Burp import should accumulate (mirrors real workflow).
    _seed_evidence(cursor, 1, {
        'tool': 'burp',
        'summary': {'by_severity': {'High': 1, 'Medium': 2}},
    })
    app_ctx.commit()

    counts = DashboardDAO().get_scan_vulnerabilities(1)
    assert counts == {'critical': 2, 'high': 6, 'medium': 9, 'low': 1}


def test_scan_vulnerabilities_combines_nessus_and_burp(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    _seed_evidence(cursor, 1, {
        'tool': 'nessus',
        'hosts': [{'ip': '10.0.0.1', 'vulnerabilities': [{'severity': 4}, {'severity': 3}]}],
    })
    _seed_evidence(cursor, 1, {
        'tool': 'burp',
        'summary': {'by_severity': {'High': 1, 'Medium': 1}},
    })
    app_ctx.commit()

    counts = DashboardDAO().get_scan_vulnerabilities(1)
    assert counts == {'critical': 1, 'high': 2, 'medium': 1, 'low': 0}


def test_scan_vulnerabilities_ignores_unrecognized_tool_metadata(app_ctx):
    """Metadata for tools we don't recognize contributes nothing to counts.

    The DB enforces JSON validity on the metadata column at INSERT time,
    so the DAO never sees malformed strings — only well-formed JSON
    objects. The cases the DAO must skip are: dicts with no tool field,
    and dicts with an unrecognized tool.
    """
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    cursor.execute(
        "INSERT INTO evidence (engagement_id, evidence_type, title, metadata) "
        "VALUES (1, 'note', 'NoTool', '{\"foo\": \"bar\"}')"
    )
    cursor.execute(
        "INSERT INTO evidence (engagement_id, evidence_type, title, metadata) "
        "VALUES (1, 'note', 'OtherTool', '{\"tool\": \"nmap\"}')"
    )
    cursor.execute(
        "INSERT INTO evidence (engagement_id, evidence_type, title, metadata) "
        "VALUES (1, 'note', 'NessusNoHosts', '{\"tool\": \"nessus\"}')"
    )
    app_ctx.commit()
    assert DashboardDAO().get_scan_vulnerabilities(1) == {
        'critical': 0, 'high': 0, 'medium': 0, 'low': 0,
    }


def test_scan_vulnerabilities_isolated_per_engagement(app_ctx):
    cursor = app_ctx.cursor()
    _seed_engagement(cursor, eid=1)
    _seed_engagement(cursor, eid=2)
    _seed_evidence(cursor, 1, {
        'tool': 'nessus',
        'hosts': [{'ip': '10.0.0.1', 'vulnerabilities': [{'severity': 4}]}],
    })
    _seed_evidence(cursor, 2, {
        'tool': 'burp',
        'summary': {'by_severity': {'High': 99}},
    })
    app_ctx.commit()

    dao = DashboardDAO()
    assert dao.get_scan_vulnerabilities(1) == {
        'critical': 1, 'high': 0, 'medium': 0, 'low': 0,
    }
    assert dao.get_scan_vulnerabilities(2) == {
        'critical': 0, 'high': 99, 'medium': 0, 'low': 0,
    }

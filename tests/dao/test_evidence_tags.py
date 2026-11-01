"""Tag filtering and autocomplete.

Regression: both read the tags/evidence_tags junction tables, which only
engagement import fills, so they returned nothing for evidence created in
the UI or API. They now use the evidence.tags string.
"""

import inspect

from flask import current_app

import routes.evidence as evidence_routes
import routes.tags as tag_routes


def _seed(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Eng A'), (2, 'Eng B')")
    cur.execute(
        "INSERT INTO evidence (engagement_id, title, evidence_type, tags) VALUES "
        "(1, 'sqli', 'note', 'critical,sql-injection'), "
        "(1, 'xss', 'note', 'high,xss,web'), "
        "(1, 'tls', 'note', 'critical'), "
        "(1, 'wild', 'note', 'a_b'), "
        "(2, 'secret', 'note', 'client-b-only,critical')"
    )
    conn.commit()


def _call(view, url):
    with current_app.test_request_context(url):
        resp = inspect.unwrap(view)()
    resp = resp[0] if isinstance(resp, tuple) else resp
    return resp.get_json()


def _titles(body):
    return sorted(r['title'] for r in body['results'])


def test_filter_single_tag(app_ctx):
    _seed(app_ctx)
    body = _call(evidence_routes.filter_evidence, '/api/evidence/filter?tags=critical')
    assert _titles(body) == ['sqli', 'tls']
    assert body['total'] == 2


def test_filter_tags_all_must_match(app_ctx):
    _seed(app_ctx)
    body = _call(evidence_routes.filter_evidence,
                 '/api/evidence/filter?tags=critical,sql-injection')
    assert _titles(body) == ['sqli']


def test_filter_tags_any(app_ctx):
    _seed(app_ctx)
    body = _call(evidence_routes.filter_evidence, '/api/evidence/filter?tags_any=xss,sql-injection')
    assert _titles(body) == ['sqli', 'xss']


def test_filter_does_not_match_partial_or_wildcard(app_ctx):
    _seed(app_ctx)
    assert _call(evidence_routes.filter_evidence, '/api/evidence/filter?tags=crit')['results'] == []
    # '_' must be literal, not a single-character wildcard
    assert _call(evidence_routes.filter_evidence, '/api/evidence/filter?tags=a%5Fb')['total'] == 1
    assert _call(evidence_routes.filter_evidence, '/api/evidence/filter?tags=aXb')['results'] == []


def test_autocomplete_counts_active_engagement_only(app_ctx):
    _seed(app_ctx)
    body = _call(tag_routes.autocomplete_tags, '/api/tags/autocomplete?q=c')
    names = [s['name'] for s in body['suggestions']]
    assert names == ['critical']           # client-b-only belongs to engagement 2
    assert body['suggestions'][0]['count'] == 2


def test_autocomplete_without_active_engagement(app_ctx):
    from flask import g
    _seed(app_ctx)
    g.active_engagement_id = None
    assert _call(tag_routes.autocomplete_tags, '/api/tags/autocomplete?q=c') == {'suggestions': []}

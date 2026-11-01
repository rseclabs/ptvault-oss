"""Full-text evidence search.

Regression: both search queries used `fts MATCH ?` (the table alias), which
SQLite rejects with "no such column: fts", so search never returned results.
"""

from models.dao.evidence_dao import EvidenceDAO


def _seed(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO engagements (id, name) VALUES (1, 'Eng A'), (2, 'Eng B')")
    cur.execute(
        "INSERT INTO evidence (engagement_id, title, content, evidence_type) VALUES "
        "(1, 'SQL injection', 'login form bypass', 'note'), "
        "(1, 'Weak TLS', 'old ciphers', 'note'), "
        "(2, 'SQL injection elsewhere', 'other client', 'note')"
    )
    conn.commit()


def test_search_fulltext_matches_within_engagement(app_ctx):
    _seed(app_ctx)
    results = EvidenceDAO().search_fulltext('injection')
    assert [r['title'] for r in results] == ['SQL injection']


def test_search_route_returns_matches(app_ctx):
    _seed(app_ctx)
    import routes.evidence as ev
    from flask import current_app
    with current_app.test_request_context('/api/evidence/search?q=injection'):
        resp = ev.search_evidence.__wrapped__.__wrapped__()
    body = resp.get_json() if hasattr(resp, 'get_json') else resp[0].get_json()
    assert [r['title'] for r in body['results']] == ['SQL injection']

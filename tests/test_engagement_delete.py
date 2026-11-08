"""Deleting an engagement removes all of it, and IDs are never reused (retest M-13).

Delete used to leave members, reports, attack maps, saved filters, test plans
and executions, relationships, attack paths and the upload folder behind, and
without AUTOINCREMENT the next engagement took the deleted one's ID and
inherited all of it. Evidence IDs were reused the same way.
"""

import importlib
import os

import pytest

from config import Config
from tests.conftest import ENGAGEMENT_A

# Every table that holds an engagement's data, and how to find its rows.
SCOPED = {
    'hosts': 'engagement_id = :e',
    'host_notes': 'host_id IN (:h)',
    'host_ports': 'host_id IN (:h)',
    'host_credentials': 'host_id IN (:h)',
    'evidence': 'engagement_id = :e',
    'evidence_tags': 'evidence_id IN (:ev)',
    'evidence_hosts': 'evidence_id IN (:ev) OR host_id IN (:h)',
    'engagement_notes': 'engagement_id = :e',
    'engagement_credentials': 'engagement_id = :e',
    'terminal_dumps': 'engagement_id = :e',
    'engagement_findings': 'engagement_id = :e',
    'engagement_members': 'engagement_id = :e',
    'reports': 'engagement_id = :e',
    'report_sections': 'report_id IN (:r)',
    'attack_maps': 'engagement_id = :e',
    'attack_map_nodes': 'map_id IN (:m)',
    'attack_map_edges': 'map_id IN (:m)',
    'saved_filters': 'engagement_id = :e',
    'test_plans': 'engagement_id = :e',
    'test_plan_items': 'test_plan_id IN (:p)',
    'test_executions': 'engagement_id = :e',
    'node_relationships': 'engagement_id = :e',
    'attack_paths': 'engagement_id = :e',
}


def _fill(conn, e, user_id):
    """One row in every engagement-scoped table for engagement e."""
    x = conn.execute
    h = x("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.1.1.1')", (e,)).lastrowid
    ev = x("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (?, 'note', 'old evidence')",
           (e,)).lastrowid
    tag = x("INSERT INTO tags (name) VALUES (?)", (f'tag-{e}',)).lastrowid
    x("INSERT INTO evidence_tags (evidence_id, tag_id) VALUES (?, ?)", (ev, tag))
    x("INSERT INTO evidence_hosts (evidence_id, host_id) VALUES (?, ?)", (ev, h))
    x("INSERT INTO host_notes (host_id, content) VALUES (?, 'n')", (h,))
    x("INSERT INTO host_ports (host_id, port, protocol, state, evidence_id) VALUES (?, 22, 'tcp', 'open', ?)", (h, ev))
    x("INSERT INTO host_credentials (host_id, username) VALUES (?, 'u')", (h,))
    x("INSERT INTO engagement_notes (engagement_id, content) VALUES (?, 'n')", (e,))
    x("INSERT INTO engagement_credentials (engagement_id, username, credential_type) VALUES (?, 'u', 'ntlm')", (e,))
    x("INSERT INTO terminal_dumps (engagement_id, title, content) VALUES (?, 't', 'c')", (e,))
    f = x("INSERT INTO engagement_findings (engagement_id, title) VALUES (?, 'f')", (e,)).lastrowid
    x("INSERT OR IGNORE INTO engagement_members (engagement_id, user_id, role) VALUES (?, ?, 'editor')", (e, user_id))
    r = x("INSERT INTO reports (engagement_id, name, structure) VALUES (?, 'OLD CLIENT REPORT', '[]')", (e,)).lastrowid
    x("INSERT INTO report_sections (report_id, section_type, title) VALUES (?, 'text', 's')", (r,))
    m = x("INSERT INTO attack_maps (engagement_id, name) VALUES (?, 'OLD CLIENT MAP')", (e,)).lastrowid
    n1 = x("INSERT INTO attack_map_nodes (map_id, node_type, label) VALUES (?, 'tactic', 'a')", (m,)).lastrowid
    n2 = x("INSERT INTO attack_map_nodes (map_id, node_type, label) VALUES (?, 'tactic', 'b')", (m,)).lastrowid
    x("INSERT INTO attack_map_edges (map_id, source_node_id, target_node_id) VALUES (?, ?, ?)", (m, n1, n2))
    x("INSERT INTO saved_filters (engagement_id, name, filter_json) VALUES (?, 'f', '{}')", (e,))
    p = x("INSERT INTO test_plans (engagement_id, name) VALUES (?, 'plan')", (e,)).lastrowid
    item = x("INSERT INTO test_plan_items (test_plan_id, custom_name) VALUES (?, 'i')", (p,)).lastrowid
    x("INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, host_id, evidence_id) "
      "VALUES (?, ?, ?, ?, ?)", (e, p, item, h, ev))
    x("INSERT INTO node_relationships (engagement_id, source_node_type, source_node_id, target_node_type, "
      "target_node_id, relationship_type) VALUES (?, 'evidence', ?, 'finding', ?, 'leads_to')", (e, ev, f))
    x("INSERT INTO attack_paths (engagement_id, name, start_evidence_id, end_evidence_id) VALUES (?, 'p', ?, ?)",
      (e, ev, ev))
    return {'e': e, 'h': h, 'ev': ev, 'r': r, 'm': m, 'p': p}


def _count(conn, table, ids):
    where = SCOPED[table]
    for name, value in sorted(ids.items(), key=lambda kv: -len(kv[0])):    # ':ev' before ':e'
        where = where.replace(f':{name}', str(value))
    return conn.execute(f'SELECT COUNT(*) FROM {table} WHERE {where}').fetchone()[0]


@pytest.fixture
def doomed(live_app):
    """Engagement 3, full of data and an upload folder; engagement A holds the same."""
    conn = live_app.db()
    conn.execute("INSERT INTO engagements (id, name) VALUES (3, 'OLD CLIENT')")
    ids = _fill(conn, 3, live_app.user_ids['editor'])
    kept = _fill(conn, ENGAGEMENT_A, live_app.user_ids['viewer'])
    template = conn.execute("INSERT INTO test_plans (engagement_id, name) VALUES (NULL, 'template')").lastrowid
    conn.commit()
    conn.close()
    folder = os.path.join(Config.UPLOAD_FOLDER, '3')
    os.makedirs(folder)
    with open(os.path.join(folder, '1_old.txt'), 'w') as f:
        f.write('old client')
    os.makedirs(os.path.join(Config.UPLOAD_FOLDER, str(ENGAGEMENT_A)), exist_ok=True)
    live_app.ids, live_app.kept, live_app.template, live_app.folder = ids, kept, template, folder
    return live_app


def test_delete_removes_every_scoped_row_and_the_upload_folder(doomed):
    admin = doomed.client_for('admin')
    assert admin.delete('/api/engagements/3').status_code == 204

    conn = doomed.db()
    left = {t: _count(conn, t, doomed.ids) for t in SCOPED if _count(conn, t, doomed.ids)}
    kept = {t: _count(conn, t, doomed.kept) for t in SCOPED}
    template = conn.execute('SELECT COUNT(*) FROM test_plans WHERE id = ?', (doomed.template,)).fetchone()[0]
    fts = conn.execute('SELECT COUNT(*) FROM evidence_fts WHERE docid = ?', (doomed.ids['ev'],)).fetchone()[0]
    conn.close()
    assert left == {}
    assert all(kept.values()), kept                                      # the other engagement is untouched
    assert template == 1 and fts == 0
    assert not os.path.exists(doomed.folder)
    assert os.path.isdir(os.path.join(Config.UPLOAD_FOLDER, str(ENGAGEMENT_A)))


def test_the_next_engagement_gets_a_new_id_and_inherits_nothing(doomed):
    admin = doomed.client_for('admin')
    assert admin.delete('/api/engagements/3').status_code == 204
    owner = doomed.client_for('editor')                                   # had an orphaned membership on 3
    resp = owner.post('/api/engagements', json={'name': 'NEWCLIENT'})
    assert resp.status_code == 201, resp.get_json()
    new_id = resp.get_json()['id']
    assert new_id > 3

    assert owner.post('/api/engagements/active', json={'engagement_id': new_id}).status_code == 200
    assert 'OLD CLIENT' not in owner.get('/api/reporting/reports').get_data(as_text=True)
    assert 'OLD CLIENT' not in owner.get('/api/attack-maps').get_data(as_text=True)
    conn = doomed.db()
    roles = conn.execute('SELECT user_id, role FROM engagement_members WHERE engagement_id = ?', (new_id,)).fetchall()
    conn.close()
    assert [tuple(r) for r in roles] == [(doomed.user_ids['editor'], 'owner')]


def test_evidence_ids_are_not_reused_and_links_go_with_the_evidence(live_app):
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    first = client.post('/api/evidence', json={'evidence_type': 'note', 'title': 'a', 'tags': 'secret-tag'}).get_json()
    conn = live_app.db()
    host = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.2.2.2')", (ENGAGEMENT_A,)).lastrowid
    conn.execute('INSERT INTO evidence_hosts (evidence_id, host_id) VALUES (?, ?)', (first['id'], host))
    tag = conn.execute("INSERT INTO tags (name) VALUES ('linked')").lastrowid
    conn.execute('INSERT INTO evidence_tags (evidence_id, tag_id) VALUES (?, ?)', (first['id'], tag))
    conn.commit()
    conn.close()
    assert client.delete(f"/api/evidence/{first['id']}").status_code == 204
    second = client.post('/api/evidence', json={'evidence_type': 'note', 'title': 'b'}).get_json()
    assert second['id'] > first['id']
    conn = live_app.db()
    links = [conn.execute(f'SELECT COUNT(*) FROM {t} WHERE evidence_id = ?', (first['id'],)).fetchone()[0]
             for t in ('evidence_tags', 'evidence_hosts')]
    conn.close()
    assert links == [0, 0]


# ------------------------------------------------------------------ the migration

def _migration():
    return importlib.import_module('models.migrations.versions.034_engagement_ids_and_orphans')


def test_migration_stops_id_reuse_and_removes_leftovers_of_deleted_engagements(test_db):
    conn = test_db
    conn.execute('PRAGMA foreign_keys = OFF')        # as in production; the old delete relied on it
    for table in ('engagements', 'evidence'):        # test_db already has 034: start from the old schema
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
        if 'AUTOINCREMENT' in sql.upper():
            _migration().downgrade(conn)
            break
    conn.execute("INSERT INTO engagements (id, name) VALUES (1, 'kept'), (2, 'deleted the old way')")
    kept, gone = _fill(conn, 1, 1), _fill(conn, 2, 2)
    conn.execute("INSERT INTO test_plans (engagement_id, name) VALUES (NULL, 'template')")
    conn.execute('DELETE FROM engagements WHERE id = 2')                 # what delete used to leave
    conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (1, 'note', 'top')")
    top = conn.execute('SELECT MAX(id) FROM evidence').fetchone()[0]
    conn.execute('INSERT INTO evidence_tags (evidence_id, tag_id) VALUES (?, 1)', (top,))
    conn.execute('DELETE FROM evidence WHERE id = ?', (top,))            # the old delete left its tag link
    conn.commit()

    _migration().upgrade(conn)
    _migration().upgrade(conn)                                           # safe to run again

    for table in ('engagements', 'evidence'):
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0]
        assert 'AUTOINCREMENT' in sql.upper(), table
    assert {t: _count(conn, t, gone) for t in SCOPED if _count(conn, t, gone)} == {}
    assert all(_count(conn, t, kept) for t in SCOPED)
    assert conn.execute("SELECT COUNT(*) FROM test_plans WHERE engagement_id IS NULL").fetchone()[0] == 1

    new_engagement = conn.execute("INSERT INTO engagements (name) VALUES ('new')").lastrowid
    new_evidence = conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title, metadata) "
                                "VALUES (1, 'note', 'findme', '{\"tool\": \"nmap\"}')").lastrowid
    assert new_engagement > 2 and new_evidence > top
    # Generated columns, indexes and the full-text triggers survive the rebuild
    assert conn.execute('SELECT tool_name FROM evidence WHERE id = ?', (new_evidence,)).fetchone()[0] == 'nmap'
    assert conn.execute("SELECT docid FROM evidence_fts WHERE evidence_fts MATCH 'findme'").fetchone()[0] == new_evidence
    indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='evidence'")}
    assert {'idx_evidence_engagement', 'idx_evidence_tool_name', 'idx_evidence_engagement_created'} <= indexes
    assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

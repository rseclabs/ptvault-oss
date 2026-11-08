"""Host delete and ID reuse (retest 2: M-16), and safe table rebuilds (L-32, L-36).

M-16: delete_host removed only the hosts row and hosts reused IDs, so the next
host, in any engagement, inherited the deleted host's credentials, notes, ports
and linked evidence. L-32: migration 034's rebuild fired ON DELETE cascades when
foreign keys were on. L-36: 034 ignored evidence references held by
relationships and attack-map nodes.
"""

import importlib

from models.migrations.manager import MigrationManager
from tests.conftest import ENGAGEMENT_A, ENGAGEMENT_B


def _host_with_everything(conn, engagement):
    x = conn.execute
    h = x("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.0.0.1')", (engagement,)).lastrowid
    ev = x("INSERT INTO evidence (engagement_id, evidence_type, title, content) VALUES (?, 'note', 'A-only', 'secret')",
           (engagement,)).lastrowid
    x("INSERT INTO evidence_hosts (evidence_id, host_id) VALUES (?, ?)", (ev, h))
    x("INSERT INTO host_credentials (host_id, username, password) VALUES (?, 'u', 'S3cret!')", (h,))
    x("INSERT INTO host_notes (host_id, content) VALUES (?, 'secret note')", (h,))
    x("INSERT INTO host_ports (host_id, port, protocol, state) VALUES (?, 445, 'tcp', 'open')", (h,))
    m = x("INSERT INTO attack_maps (engagement_id, name) VALUES (?, 'm')", (engagement,)).lastrowid
    x("INSERT INTO attack_map_nodes (map_id, node_type, label, ref_type, ref_id) VALUES (?, 'host_ref', 'h', 'host', ?)",
      (m, h))
    p = x("INSERT INTO test_plans (engagement_id, name) VALUES (?, 'p')", (engagement,)).lastrowid
    i = x("INSERT INTO test_plan_items (test_plan_id, custom_name) VALUES (?, 'i')", (p,)).lastrowid
    x("INSERT INTO test_executions (engagement_id, test_plan_id, test_plan_item_id, host_id) VALUES (?, ?, ?, ?)",
      (engagement, p, i, h))
    return h, ev


CHILDREN = ('host_credentials', 'host_notes', 'host_ports', 'evidence_hosts', 'test_executions')


def test_deleting_a_host_removes_what_hangs_off_it_and_its_id_is_not_reused(live_app):
    conn = live_app.db()
    h, ev = _host_with_everything(conn, ENGAGEMENT_A)
    conn.commit()
    conn.close()
    owner = live_app.client_for('owner', active_engagement=ENGAGEMENT_A)
    assert owner.delete(f'/api/hosts/{h}').status_code == 204

    conn = live_app.db()
    left = {t: conn.execute(f'SELECT COUNT(*) FROM {t} WHERE host_id = ?', (h,)).fetchone()[0] for t in CHILDREN}
    ref = conn.execute("SELECT ref_id FROM attack_map_nodes WHERE ref_type = 'host' OR ref_type IS NULL").fetchone()
    conn.close()
    assert left == dict.fromkeys(CHILDREN, 0)
    assert ref[0] is None                                              # the map node keeps its label, loses the link

    outsider = live_app.client_for('outsider', active_engagement=ENGAGEMENT_B)
    new = outsider.post('/api/hosts', json={'ip': '10.9.9.9'}).get_json()
    assert new['id'] > h
    assert 'S3cret' not in outsider.get(f"/api/hosts/{new['id']}/credentials").get_data(as_text=True)


def test_host_view_lists_only_its_own_engagements_evidence(live_app):
    conn = live_app.db()
    h, _ = _host_with_everything(conn, ENGAGEMENT_A)
    b_ev = conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (?, 'note', 'B stray')",
                        (ENGAGEMENT_B,)).lastrowid
    conn.execute('INSERT INTO evidence_hosts (evidence_id, host_id) VALUES (?, ?)', (b_ev, h))
    conn.commit()
    conn.close()
    body = live_app.client_for('owner', active_engagement=ENGAGEMENT_A).get(f'/api/hosts/{h}').get_data(as_text=True)
    assert 'A-only' in body and 'B stray' not in body


# ------------------------------------------------------------------ migrations

def _migration(name):
    return importlib.import_module(f'models.migrations.versions.{name}')


def test_migration_036_stops_host_id_reuse_and_purges_dangling_links(test_db):
    conn = test_db
    m036 = _migration('036_host_ids_and_links')
    conn.execute('PRAGMA foreign_keys = OFF')                                   # as in production
    m036.downgrade(conn)
    conn.execute('DELETE FROM schema_migrations WHERE version = 36')                                   # as in production
    conn.execute("INSERT INTO engagements (id, name) VALUES (1, 'E')")
    h, ev = _host_with_everything(conn, 1)
    conn.execute('DELETE FROM hosts WHERE id = ?', (h,))                         # the old delete
    # evidence deleted the old way, still named by a relationship and a map node
    gone_ev = conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (1, 'note', 'top')").lastrowid
    f = conn.execute("INSERT INTO engagement_findings (engagement_id, title) VALUES (1, 'f')").lastrowid
    conn.execute("INSERT INTO node_relationships (engagement_id, source_node_type, source_node_id, target_node_type, "
                 "target_node_id, relationship_type) VALUES (1, 'evidence', ?, 'finding', ?, 'leads_to')", (gone_ev, f))
    conn.execute("UPDATE attack_map_nodes SET ref_type = 'evidence', ref_id = ?", (gone_ev,))
    conn.execute('DELETE FROM evidence WHERE id = ?', (gone_ev,))
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'evidence'")         # as before 034 knew of it
    conn.commit()

    assert MigrationManager(conn).apply_migration(36, 'host_ids_and_links', m036)
    assert 'AUTOINCREMENT' in conn.execute("SELECT sql FROM sqlite_master WHERE name = 'hosts'").fetchone()[0].upper()
    assert {t: conn.execute(f'SELECT COUNT(*) FROM {t} WHERE host_id = ?', (h,)).fetchone()[0] for t in CHILDREN} \
        == dict.fromkeys(CHILDREN, 0)
    assert conn.execute('SELECT COUNT(*) FROM node_relationships').fetchone()[0] == 0
    assert conn.execute('SELECT ref_id FROM attack_map_nodes').fetchone()[0] is None
    new_host = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (1, '10.0.0.2')").lastrowid
    new_ev = conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (1, 'note', 'n')").lastrowid
    assert new_host > h and new_ev > gone_ev
    assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_rebuilds_keep_child_rows_when_foreign_keys_are_on(test_db):
    """L-32: the manager turns foreign keys off around a rebuild, as SQLite requires."""
    conn = test_db
    m034 = _migration('034_engagement_ids_and_orphans')
    conn.execute('PRAGMA foreign_keys = OFF')
    m034.downgrade(conn)
    conn.execute('DELETE FROM schema_migrations WHERE version = 34')
    conn.commit()
    conn.execute('PRAGMA foreign_keys = ON')
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    conn.execute("INSERT INTO users (id, username, email, password_hash, role) VALUES (1, 'u', 'u@x.co', 'h', 'tester')")
    conn.execute("INSERT INTO engagements (id, name) VALUES (1, 'E')")
    conn.execute("INSERT INTO engagement_members (engagement_id, user_id, role) VALUES (1, 1, 'owner')")
    h = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (1, '10.0.0.1')").lastrowid
    conn.execute("INSERT INTO host_credentials (host_id, username) VALUES (?, 'u')", (h,))
    conn.commit()
    assert MigrationManager(conn).apply_migration(34, 'engagement_ids_and_orphans', m034)
    counts = [conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
              for t in ('engagement_members', 'hosts', 'host_credentials')]
    assert counts == [1, 1, 1]
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1               # restored afterwards

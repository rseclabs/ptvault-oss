"""M-2: engagement scoping fails closed, and map/relationship children are checked.

With no active engagement, engagement-scoped DAOs return nothing and refuse
to insert. Attack-map node and edge routes act only on maps in the active
engagement, and a relationship can only link nodes of the active engagement.
"""

import pytest
from flask import Flask, g

from tests.conftest import ENGAGEMENT_A, ENGAGEMENT_B


@pytest.fixture
def maps(live_app):
    conn = live_app.db()
    ids = {}
    for name, eng in (('a', ENGAGEMENT_A), ('b', ENGAGEMENT_B)):
        ids[f'map_{name}'] = conn.execute(
            "INSERT INTO attack_maps (engagement_id, name) VALUES (?, ?)", (eng, f'Map {name}')).lastrowid
        n1 = conn.execute("INSERT INTO attack_map_nodes (map_id, node_type, x, y, label) VALUES (?, 'recon', 1, 1, ?)",
                          (ids[f'map_{name}'], f'{name}-node-1')).lastrowid
        n2 = conn.execute("INSERT INTO attack_map_nodes (map_id, node_type, x, y, label) VALUES (?, 'recon', 2, 2, ?)",
                          (ids[f'map_{name}'], f'{name}-node-2')).lastrowid
        ids[f'nodes_{name}'] = (n1, n2)
        ids[f'edge_{name}'] = conn.execute(
            "INSERT INTO attack_map_edges (map_id, source_node_id, target_node_id) VALUES (?, ?, ?)",
            (ids[f'map_{name}'], n1, n2)).lastrowid
        ids[f'evidence_{name}'] = [conn.execute(
            "INSERT INTO evidence (engagement_id, evidence_type, title) VALUES (?, 'note', ?)",
            (eng, f'{name}-evidence-{i}')).lastrowid for i in (1, 2)]
    conn.commit()
    conn.close()
    live_app.ids = ids
    return live_app


def _one(live, sql, params=()):
    conn = live.db()
    value = conn.execute(sql, params).fetchone()
    conn.close()
    return value


# ------------------------------------------------------------- BaseDAO

def test_scoped_dao_without_active_engagement_reads_nothing_and_refuses_inserts(test_db):
    from models.dao.attack_map_dao import AttackMapDAO
    test_db.execute("INSERT INTO engagements (id, name) VALUES (1, 'E')")
    test_db.execute("INSERT INTO attack_maps (engagement_id, name) VALUES (1, 'm')")
    test_db.commit()

    with Flask(__name__).app_context():
        g.db = test_db
        g.active_engagement_id = None
        dao = AttackMapDAO()
        assert dao.find_all() == []
        assert dao.find_by_id(1) is None
        with pytest.raises(ValueError):
            dao.create({'name': 'unscoped'})
        assert dao.delete(1) is False
    assert test_db.execute('SELECT COUNT(*) FROM attack_maps').fetchone()[0] == 1


def test_attack_maps_list_is_empty_without_active_engagement(maps):
    resp = maps.client_for('admin').get('/api/attack-maps')
    assert resp.status_code == 200
    assert resp.get_json() in ([], {'maps': []})


def test_attack_map_of_other_engagement_is_not_readable(maps):
    client = maps.client_for('outsider', active_engagement=ENGAGEMENT_B)
    assert client.get(f"/api/attack-maps/{maps.ids['map_a']}").status_code == 404


# ------------------------------------------------------------- map children

def test_node_of_other_engagement_map_cannot_be_updated(maps):
    client = maps.client_for('outsider', active_engagement=ENGAGEMENT_B)
    node = maps.ids['nodes_a'][0]
    resp = client.put(f"/api/attack-maps/{maps.ids['map_a']}/nodes/{node}", json={'label': 'pwned'})
    assert resp.status_code == 404
    assert _one(maps, 'SELECT label FROM attack_map_nodes WHERE id = ?', (node,))[0] == 'a-node-1'


def test_node_of_other_engagement_map_cannot_be_deleted(maps):
    client = maps.client_for('outsider', active_engagement=ENGAGEMENT_B)
    node = maps.ids['nodes_a'][0]
    assert client.delete(f"/api/attack-maps/{maps.ids['map_a']}/nodes/{node}").status_code == 404
    assert _one(maps, 'SELECT COUNT(*) FROM attack_map_nodes WHERE id = ?', (node,))[0] == 1


def test_edges_of_other_engagement_map_are_protected(maps):
    client = maps.client_for('outsider', active_engagement=ENGAGEMENT_B)
    a1, a2 = maps.ids['nodes_a']
    resp = client.post(f"/api/attack-maps/{maps.ids['map_a']}/edges",
                       json={'source_node_id': a2, 'target_node_id': a1})
    assert resp.status_code == 404
    assert client.delete(f"/api/attack-maps/{maps.ids['map_a']}/edges/{maps.ids['edge_a']}").status_code == 404
    assert _one(maps, 'SELECT COUNT(*) FROM attack_map_edges WHERE map_id = ?', (maps.ids['map_a'],))[0] == 1


def test_batch_position_update_only_moves_nodes_of_that_map(maps):
    client = maps.client_for('outsider', active_engagement=ENGAGEMENT_B)
    a_node, b_node = maps.ids['nodes_a'][0], maps.ids['nodes_b'][0]
    resp = client.put(f"/api/attack-maps/{maps.ids['map_b']}/nodes/batch",
                      json={'updates': [{'id': a_node, 'x': 999, 'y': 999}, {'id': b_node, 'x': 50, 'y': 60}]})
    assert resp.status_code == 200
    assert tuple(_one(maps, 'SELECT x, y FROM attack_map_nodes WHERE id = ?', (a_node,))) == (1, 1)
    assert tuple(_one(maps, 'SELECT x, y FROM attack_map_nodes WHERE id = ?', (b_node,))) == (50, 60)

    # The batch route on another engagement's map is refused outright.
    resp = client.put(f"/api/attack-maps/{maps.ids['map_a']}/nodes/batch",
                      json={'updates': [{'id': a_node, 'x': 7, 'y': 7}]})
    assert resp.status_code == 404


def test_member_can_still_edit_own_map(maps):
    client = maps.client_for('editor', active_engagement=ENGAGEMENT_A)
    node = maps.ids['nodes_a'][0]
    assert client.put(f"/api/attack-maps/{maps.ids['map_a']}/nodes/{node}",
                      json={'label': 'edited'}).status_code == 200
    a1, a2 = maps.ids['nodes_a']
    assert client.post(f"/api/attack-maps/{maps.ids['map_a']}/edges",
                       json={'source_node_id': a2, 'target_node_id': a1}).status_code in (200, 201)


# ------------------------------------------------------------- relationships

def test_relationship_cannot_link_nodes_of_another_engagement(maps):
    client = maps.client_for('outsider', active_engagement=ENGAGEMENT_B)
    a1, _ = maps.ids['evidence_a']
    b1, _ = maps.ids['evidence_b']
    resp = client.post('/api/relationships', json={
        'source_node_type': 'evidence', 'source_node_id': b1,
        'target_node_type': 'evidence', 'target_node_id': a1, 'type': 'leads_to'})
    assert resp.status_code == 400
    assert _one(maps, 'SELECT COUNT(*) FROM node_relationships')[0] == 0


def test_relationship_within_engagement_is_created(maps):
    client = maps.client_for('editor', active_engagement=ENGAGEMENT_A)
    a1, a2 = maps.ids['evidence_a']
    resp = client.post('/api/relationships', json={
        'source_node_type': 'evidence', 'source_node_id': a1,
        'target_node_type': 'evidence', 'target_node_id': a2, 'type': 'leads_to'})
    assert resp.status_code == 201
    assert _one(maps, 'SELECT engagement_id FROM node_relationships')[0] == ENGAGEMENT_A

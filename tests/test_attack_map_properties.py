"""Attack map node properties must be an object (retest note, not security).

PUT .../nodes/<id> accepted {"properties": null} (or a string, a list...), and
the map's SVG export then failed with 500 calling .get() on it.
"""

import pytest

from tests.conftest import ENGAGEMENT_A


@pytest.fixture
def node(live_app):
    client = live_app.client_for('editor', active_engagement=ENGAGEMENT_A)
    m = client.post('/api/attack-maps', json={'name': 'm'}).get_json()
    n = client.post(f"/api/attack-maps/{m['id']}/nodes", json={'node_type': 'tactic', 'label': 'a'}).get_json()
    live_app.client, live_app.map_id, live_app.node_id = client, m['id'], n['id']
    return live_app


@pytest.mark.parametrize('value', [None, 'text', ['a'], 5, '[1]'])
def test_update_accepts_only_an_object(node, value):
    resp = node.client.put(f'/api/attack-maps/{node.map_id}/nodes/{node.node_id}', json={'properties': value})
    if value is None:
        assert resp.status_code == 200 and resp.get_json()['properties'] == {}     # null clears them
    else:
        assert resp.status_code == 400
    assert node.client.get(f'/api/attack-maps/{node.map_id}/svg').status_code == 200


@pytest.mark.parametrize('value', ['text', ['a'], 5])
def test_create_accepts_only_an_object(node, value):
    resp = node.client.post(f'/api/attack-maps/{node.map_id}/nodes',
                            json={'node_type': 'tactic', 'label': 'b', 'properties': value})
    assert resp.status_code == 400


def test_svg_export_survives_stored_non_objects(node):
    conn = node.db()
    conn.execute("UPDATE attack_map_nodes SET properties = 'null' WHERE id = ?", (node.node_id,))
    conn.commit()
    conn.close()
    assert node.client.get(f'/api/attack-maps/{node.map_id}/svg').status_code == 200


def test_objects_still_work(node):
    resp = node.client.put(f'/api/attack-maps/{node.map_id}/nodes/{node.node_id}',
                           json={'properties': {'ttp': 'T1059'}})
    assert resp.status_code == 200 and resp.get_json()['properties'] == {'ttp': 'T1059'}
    assert 'T1059' in node.client.get(f'/api/attack-maps/{node.map_id}/svg').get_data(as_text=True)

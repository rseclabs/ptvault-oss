"""Unit tests for node relationship mapping.

Tests RelationshipDAO and AttackPathDAO against the universal node-typed
schema introduced in migration 014. find_path() filters node_relationships
to evidence-to-evidence edges, since the API still takes evidence IDs.
"""

import pytest

from models.dao.relationship_dao import RelationshipDAO, AttackPathDAO


def _seed_evidence(test_db, engagement_id=1, count=5):
    """Insert N evidence rows into the engagement and return their IDs."""
    cursor = test_db.cursor()
    titles = [
        'Initial Scan', 'Found Credentials', 'SSH Access',
        'Privilege Escalation', 'Lateral Movement',
    ]
    types = ['tool_output', 'note', 'command_output', 'command_output', 'note']
    ids = []
    for i in range(count):
        cursor.execute(
            'INSERT INTO evidence (engagement_id, title, evidence_type, content) '
            'VALUES (?, ?, ?, ?)',
            (engagement_id, titles[i % 5], types[i % 5], f'Body for {titles[i % 5]}'),
        )
        ids.append(cursor.lastrowid)
    test_db.commit()
    return ids


def _create(dao, src_id, tgt_id, rel_type, label=None, description=None):
    """Convenience: create an evidence-to-evidence relationship."""
    return dao.create_relationship(
        source_node_type='evidence', source_node_id=src_id,
        target_node_type='evidence', target_node_id=tgt_id,
        relationship_type=rel_type, label=label, description=description,
    )


def test_create_relationship(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    rel_id = _create(
        dao, eids[0], eids[1], 'discovers',
        label='Scan found credentials',
        description='Nmap scan discovered admin credentials in config file',
    )

    assert rel_id > 0

    rel = dao.find_by_id(rel_id)
    assert rel is not None
    assert rel['source_node_type'] == 'evidence'
    assert rel['source_node_id'] == eids[0]
    assert rel['target_node_id'] == eids[1]
    assert rel['relationship_type'] == 'discovers'


def test_prevent_self_relationship(app_ctx, sample_engagement):
    _seed_evidence(app_ctx, count=1)
    dao = RelationshipDAO()

    with pytest.raises(ValueError):
        _create(dao, 1, 1, 'uses')


def test_get_relationships_for_node(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    _create(dao, eids[0], eids[1], 'discovers')
    _create(dao, eids[1], eids[2], 'uses')
    _create(dao, eids[2], eids[3], 'escalates')

    relationships = dao.get_relationships_for_node('evidence', eids[1])
    assert len(relationships) == 2

    source_ids = [r['source_node_id'] for r in relationships]
    target_ids = [r['target_node_id'] for r in relationships]
    assert eids[0] in source_ids   # incoming from eids[0]
    assert eids[2] in target_ids   # outgoing to eids[2]


def test_get_graph_data(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    _create(dao, eids[0], eids[1], 'discovers')
    _create(dao, eids[1], eids[2], 'uses')
    _create(dao, eids[2], eids[3], 'escalates')

    graph = dao.get_graph_data()

    assert 'nodes' in graph
    assert 'edges' in graph
    # All seeded evidence nodes show up (sample_engagement also creates some)
    evidence_nodes = [n for n in graph['nodes'] if n.get('node_type') == 'evidence']
    assert len(evidence_nodes) >= len(eids)
    assert len(graph['edges']) == 3


def test_delete_by_node(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    _create(dao, eids[0], eids[1], 'discovers')
    _create(dao, eids[1], eids[2], 'uses')
    _create(dao, eids[1], eids[3], 'leads_to')

    count = dao.delete_by_node('evidence', eids[1])
    assert count == 3

    relationships = dao.get_relationships_for_node('evidence', eids[1])
    assert len(relationships) == 0


def test_relationship_statistics(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    _create(dao, eids[0], eids[1], 'discovers')
    _create(dao, eids[1], eids[2], 'uses')
    _create(dao, eids[2], eids[3], 'uses')
    _create(dao, eids[3], eids[4], 'escalates')

    stats = dao.get_relationship_statistics()
    assert stats['total'] == 4
    assert stats['discovers'] == 1
    assert stats['uses'] == 2
    assert stats['escalates'] == 1


def test_find_path_simple(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    _create(dao, eids[0], eids[1], 'discovers')
    _create(dao, eids[1], eids[2], 'uses')

    path = dao.find_path(eids[0], eids[2])
    assert len(path) == 3


def test_find_path_complex(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    _create(dao, eids[0], eids[1], 'discovers')
    _create(dao, eids[1], eids[2], 'uses')
    _create(dao, eids[2], eids[3], 'escalates')
    _create(dao, eids[3], eids[4], 'leads_to')

    path = dao.find_path(eids[0], eids[4])
    assert len(path) == 5


def test_find_path_no_connection(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = RelationshipDAO()

    _create(dao, eids[0], eids[1], 'discovers')
    _create(dao, eids[3], eids[4], 'uses')

    path = dao.find_path(eids[0], eids[4])
    assert len(path) == 0


def test_save_attack_path(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = AttackPathDAO()

    path_data = [
        {'id': eids[0], 'title': 'Initial Scan'},
        {'id': eids[1], 'title': 'Found Credentials'},
        {'id': eids[2], 'title': 'SSH Access'},
    ]

    path_id = dao.save_path(
        name='Initial Access',
        start_id=eids[0],
        end_id=eids[2],
        path_data=path_data,
        description='Path from reconnaissance to initial access',
    )
    assert path_id > 0

    path = dao.get_path(path_id)
    assert path is not None
    assert path['name'] == 'Initial Access'
    assert path['start_evidence_id'] == eids[0]
    assert path['end_evidence_id'] == eids[2]
    assert len(path['path_data']) == 3


def test_list_attack_paths(app_ctx, sample_engagement):
    eids = _seed_evidence(app_ctx)
    dao = AttackPathDAO()

    dao.save_path('Path 1', eids[0], eids[2], [{'id': eids[0]}, {'id': eids[1]}, {'id': eids[2]}])
    dao.save_path('Path 2', eids[1], eids[4], [{'id': eids[1]}, {'id': eids[2]}, {'id': eids[3]}, {'id': eids[4]}])

    paths = dao.list_paths()
    assert len(paths) == 2
    assert any(p['name'] == 'Path 1' for p in paths)
    assert any(p['name'] == 'Path 2' for p in paths)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

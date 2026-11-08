"""Data Access Objects for Attack Maps.

Provides CRUD operations for attack maps, nodes, and edges.
Maps are engagement-scoped; nodes and edges are scoped via map_id.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from flask import g

from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class AttackMapDAO(BaseDAO):
    """DAO for attack_maps table. Engagement-scoped."""

    def __init__(self):
        super().__init__('attack_maps', engagement_scoped=True)

    def get_full_map(self, map_id: int) -> Optional[Dict[str, Any]]:
        """Get a map with all its nodes and edges."""
        attack_map = self.find_by_id(map_id)
        if not attack_map:
            return None

        node_dao = AttackMapNodeDAO()
        edge_dao = AttackMapEdgeDAO()

        attack_map['nodes'] = node_dao.find_all(
            filters={'map_id': map_id},
            order_by='id'
        )
        attack_map['edges'] = edge_dao.find_all(
            filters={'map_id': map_id},
            order_by='id'
        )

        # Parse JSON properties on nodes
        for node in attack_map['nodes']:
            if node.get('properties') and isinstance(node['properties'], str):
                try:
                    node['properties'] = json.loads(node['properties'])
                except (json.JSONDecodeError, TypeError):
                    node['properties'] = {}

        # Parse canvas_data
        if attack_map.get('canvas_data') and isinstance(attack_map['canvas_data'], str):
            try:
                attack_map['canvas_data'] = json.loads(attack_map['canvas_data'])
            except (json.JSONDecodeError, TypeError):
                attack_map['canvas_data'] = {}

        return attack_map

    def duplicate_map(self, map_id: int) -> Optional[int]:
        """Duplicate a map with all its nodes and edges. Returns new map ID."""
        source = self.get_full_map(map_id)
        if not source:
            return None

        # Create new map
        new_map_id = self.create({
            'name': f"{source['name']} (Copy)",
            'description': source.get('description', ''),
            'canvas_data': json.dumps(source.get('canvas_data', {})) if source.get('canvas_data') else None,
            'created_by': getattr(g, 'user_id', None)
        })

        node_dao = AttackMapNodeDAO()
        edge_dao = AttackMapEdgeDAO()

        # Map old node IDs to new node IDs
        node_id_map = {}

        for node in source.get('nodes', []):
            old_id = node['id']
            props = node.get('properties', {})
            if isinstance(props, dict):
                props = json.dumps(props)
            new_node_id = node_dao.create({
                'map_id': new_map_id,
                'node_type': node['node_type'],
                'x': node['x'],
                'y': node['y'],
                'width': node.get('width', 220),
                'height': node.get('height', 80),
                'label': node.get('label', ''),
                'properties': props,
                'ref_id': node.get('ref_id'),
                'ref_type': node.get('ref_type')
            })
            node_id_map[old_id] = new_node_id

        for edge in source.get('edges', []):
            new_source = node_id_map.get(edge['source_node_id'])
            new_target = node_id_map.get(edge['target_node_id'])
            if new_source and new_target:
                edge_dao.create({
                    'map_id': new_map_id,
                    'source_node_id': new_source,
                    'target_node_id': new_target,
                    'label': edge.get('label', '')
                })

        return new_map_id


class AttackMapNodeDAO(BaseDAO):
    """DAO for attack_map_nodes table. Not engagement-scoped (scoped via map_id)."""

    def __init__(self):
        super().__init__('attack_map_nodes', engagement_scoped=False)

    def batch_update_positions(self, map_id: int, updates: List[Dict[str, Any]]) -> int:
        """Batch update positions of nodes on one map. Returns count of updated nodes.

        Node ids that are not on map_id are ignored.
        """
        cursor = self.db.cursor()
        count = 0
        for update in updates:
            node_id = update.get('id')
            x = update.get('x')
            y = update.get('y')
            if node_id is not None and x is not None and y is not None:
                cursor.execute(
                    'UPDATE attack_map_nodes SET x = ?, y = ? WHERE id = ? AND map_id = ?',
                    (x, y, node_id, map_id)
                )
                count += cursor.rowcount
        self.db.commit()
        return count


class AttackMapEdgeDAO(BaseDAO):
    """DAO for attack_map_edges table. Not engagement-scoped (scoped via map_id)."""

    def __init__(self):
        super().__init__('attack_map_edges', engagement_scoped=False)

    def delete_by_node(self, node_id: int) -> int:
        """Delete all edges connected to a node. Returns count of deleted edges."""
        cursor = self.db.cursor()
        cursor.execute(
            'DELETE FROM attack_map_edges WHERE source_node_id = ? OR target_node_id = ?',
            (node_id, node_id)
        )
        self.db.commit()
        return cursor.rowcount

"""Data Access Object for evidence relationships.

This module handles CRUD operations for evidence relationships and provides
graph traversal methods for finding attack paths between evidence items.
"""

import logging
from typing import List, Dict, Optional
from collections import deque

from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class RelationshipDAO(BaseDAO):
    """DAO for node relationships (evidence, findings, notes, credentials)."""

    def __init__(self):
        """Initialize RelationshipDAO."""
        super().__init__('node_relationships', engagement_scoped=True)

    def create_relationship(self, source_node_type: str, source_node_id: int,
                           target_node_type: str, target_node_id: int,
                           relationship_type: str, label: str = None,
                           description: str = None, created_by: int = None) -> int:
        """Create node relationship.

        Args:
            source_node_type: Type of source node (evidence, finding, note, credential)
            source_node_id: Source node ID
            target_node_type: Type of target node (evidence, finding, note, credential)
            target_node_id: Target node ID
            relationship_type: Type of relationship (leads_to, uses, discovers, exploits, escalates, custom)
            label: Optional custom label for the relationship
            description: Optional explanation of the relationship
            created_by: User ID who created the relationship

        Returns:
            int: ID of newly created relationship

        Raises:
            ValueError: If source and target are the same node
        """
        if source_node_type == target_node_type and source_node_id == target_node_id:
            raise ValueError("Cannot create relationship from node to itself")
        for node_type, node_id in ((source_node_type, source_node_id), (target_node_type, target_node_id)):
            if not self.node_in_engagement(node_type, node_id):
                raise ValueError(f"{node_type} {node_id} not found in the active engagement")

        data = {
            'source_node_type': source_node_type,
            'source_node_id': source_node_id,
            'target_node_type': target_node_type,
            'target_node_id': target_node_id,
            'relationship_type': relationship_type,
            'label': label,
            'description': description,
            'created_by': created_by
        }

        rel_id = self.create(data)
        logger.info(f"Created relationship: {source_node_type}_{source_node_id} -> {target_node_type}_{target_node_id} ({relationship_type})")
        return rel_id

    # Where each node type lives; notes and credentials belong either to the
    # engagement directly or to one of its hosts.
    _NODE_LOOKUPS = {
        'evidence': ['SELECT 1 FROM evidence WHERE id = ? AND engagement_id = ?'],
        'finding': ['SELECT 1 FROM engagement_findings WHERE id = ? AND engagement_id = ?'],
        'note': ['SELECT 1 FROM engagement_notes WHERE id = ? AND engagement_id = ?',
                 'SELECT 1 FROM host_notes n JOIN hosts h ON n.host_id = h.id WHERE n.id = ? AND h.engagement_id = ?'],
        'credential': ['SELECT 1 FROM engagement_credentials WHERE id = ? AND engagement_id = ?',
                       'SELECT 1 FROM host_credentials c JOIN hosts h ON c.host_id = h.id '
                       'WHERE c.id = ? AND h.engagement_id = ?'],
    }

    def node_in_engagement(self, node_type: str, node_id: int) -> bool:
        """True if the node exists in the active engagement."""
        if not self.engagement_id:
            return False
        cursor = self.db.cursor()
        for query in self._NODE_LOOKUPS.get(node_type, []):
            cursor.execute(query, (node_id, self.engagement_id))
            if cursor.fetchone():
                return True
        return False

    def get_relationships_for_node(self, node_type: str, node_id: int) -> List[Dict]:
        """Get all relationships for a node (both incoming and outgoing).

        Args:
            node_type: Type of node (evidence, finding, note, credential)
            node_id: Node ID

        Returns:
            List of relationship dictionaries with source and target titles
        """
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT r.*
            FROM node_relationships r
            WHERE ((r.source_node_type = ? AND r.source_node_id = ?)
               OR (r.target_node_type = ? AND r.target_node_id = ?))
            AND r.engagement_id = ?
            ORDER BY r.created_at DESC
        ''', (node_type, node_id, node_type, node_id, self.engagement_id))

        return [dict(row) for row in cursor.fetchall()]

    def get_outgoing_relationships(self, node_type: str, node_id: int) -> List[Dict]:
        """Get outgoing relationships from a node.

        Args:
            node_type: Type of node (evidence, finding, note, credential)
            node_id: Node ID

        Returns:
            List of relationship dictionaries
        """
        return self.find_all({'source_node_type': node_type, 'source_node_id': node_id}, order_by='created_at DESC')

    def get_incoming_relationships(self, node_type: str, node_id: int) -> List[Dict]:
        """Get incoming relationships to a node.

        Args:
            node_type: Type of node (evidence, finding, note, credential)
            node_id: Node ID

        Returns:
            List of relationship dictionaries
        """
        return self.find_all({'target_node_type': node_type, 'target_node_id': node_id}, order_by='created_at DESC')

    def find_path(self, start_id: int, end_id: int) -> List[Dict]:
        """Find shortest path between two evidence items using BFS.

        Args:
            start_id: Starting evidence ID
            end_id: Target evidence ID

        Returns:
            List of evidence dictionaries representing the path, empty if no path exists
        """
        # Build adjacency list — only consider evidence-to-evidence edges,
        # since find_path takes evidence IDs. node_relationships replaced
        # the dropped evidence_relationships table in migration 014.
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT source_node_id, target_node_id, relationship_type, label
            FROM node_relationships
            WHERE engagement_id = ?
              AND source_node_type = 'evidence'
              AND target_node_type = 'evidence'
        ''', (self.engagement_id,))

        # Build graph
        graph = {}
        edge_info = {}  # Store edge metadata
        for row in cursor.fetchall():
            source, target, rel_type, label = row[0], row[1], row[2], row[3]
            if source not in graph:
                graph[source] = []
            graph[source].append(target)
            edge_info[(source, target)] = {'type': rel_type, 'label': label}

        # BFS to find shortest path
        queue = deque([(start_id, [start_id])])
        visited = {start_id}

        while queue:
            node, path = queue.popleft()
            if node == end_id:
                return self._get_path_details(path, edge_info)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        logger.info(f"No path found between evidence {start_id} and {end_id}")
        return []

    def _get_path_details(self, evidence_ids: List[int], edge_info: Dict) -> List[Dict]:
        """Get evidence details for path with edge information.

        Args:
            evidence_ids: List of evidence IDs in path order
            edge_info: Dictionary mapping (source, target) tuples to edge metadata

        Returns:
            List of path step dictionaries with evidence and edge details
        """
        if not evidence_ids:
            return []

        cursor = self.db.cursor()
        placeholders = ','.join('?' * len(evidence_ids))
        cursor.execute(f'''
            SELECT
                e.id,
                e.title,
                e.evidence_type,
                e.created_at,
                e.tags,
                GROUP_CONCAT(DISTINCT eh.host_id) as host_ids
            FROM evidence e
            LEFT JOIN evidence_hosts eh ON e.id = eh.evidence_id
            WHERE e.id IN ({placeholders}) AND e.engagement_id = ?
            GROUP BY e.id
        ''', [*evidence_ids, self.engagement_id])          # only the active engagement's evidence (M-15)

        evidence_map = {}
        for row in cursor.fetchall():
            evidence_dict = dict(row)
            # Convert comma-separated host_ids to list of integers
            if evidence_dict.get('host_ids'):
                evidence_dict['host_ids'] = [int(h) for h in evidence_dict['host_ids'].split(',')]
            else:
                evidence_dict['host_ids'] = []
            evidence_map[evidence_dict['id']] = evidence_dict

        # Build path with edge information
        path_details = []
        for i, eid in enumerate(evidence_ids):
            if eid in evidence_map:
                step = evidence_map[eid].copy()

                # Add edge info if not the last item
                if i < len(evidence_ids) - 1:
                    next_id = evidence_ids[i + 1]
                    edge = edge_info.get((eid, next_id), {})
                    step['edge_type'] = edge.get('type')
                    step['edge_label'] = edge.get('label')

                path_details.append(step)

        return path_details

    def get_graph_data(self) -> Dict[str, List]:
        """Get complete relationship graph for visualization.

        Returns:
            Dictionary with 'nodes' and 'edges' lists for graph rendering
        """
        cursor = self.db.cursor()
        nodes = []

        # Get all evidence nodes with their associated hosts
        cursor.execute('''
            SELECT
                'evidence' as node_type,
                e.id,
                e.title,
                e.evidence_type as type,
                e.tags,
                e.created_at,
                GROUP_CONCAT(DISTINCT eh.host_id) as host_ids
            FROM evidence e
            LEFT JOIN evidence_hosts eh ON e.id = eh.evidence_id
            WHERE e.engagement_id = ?
            GROUP BY e.id
        ''', (self.engagement_id,))

        for row in cursor.fetchall():
            node = dict(row)
            # Create unique ID combining type and database ID
            node['unique_id'] = f"{node['node_type']}_{node['id']}"
            # Convert comma-separated host_ids to list of integers
            if node.get('host_ids'):
                node['host_ids'] = [int(h) for h in node['host_ids'].split(',')]
            else:
                node['host_ids'] = []
            nodes.append(node)

        # Get all findings as nodes
        cursor.execute('''
            SELECT
                'finding' as node_type,
                id,
                title,
                criticality as type,
                '' as tags,
                created_at,
                ip_address,
                hostname
            FROM engagement_findings
            WHERE engagement_id = ?
        ''', (self.engagement_id,))

        for row in cursor.fetchall():
            node = dict(row)
            # Create unique ID combining type and database ID
            node['unique_id'] = f"{node['node_type']}_{node['id']}"
            # Findings don't use the host_ids array, but include ip/hostname
            node['host_ids'] = []
            nodes.append(node)

        # Get all host notes as nodes
        cursor.execute('''
            SELECT
                'note' as node_type,
                hn.id,
                'Note: ' || SUBSTR(hn.content, 1, 50) || '...' as title,
                'note' as type,
                '' as tags,
                hn.created_at,
                hn.host_id
            FROM host_notes hn
            JOIN hosts h ON hn.host_id = h.id
            WHERE h.engagement_id = ?
        ''', (self.engagement_id,))

        for row in cursor.fetchall():
            node = dict(row)
            # Create unique ID combining type and database ID
            node['unique_id'] = f"{node['node_type']}_{node['id']}"
            node['host_ids'] = [node['host_id']] if node.get('host_id') else []
            nodes.append(node)

        # Get all engagement notes as nodes (General section)
        cursor.execute('''
            SELECT
                'note' as node_type,
                id,
                'Note: ' || SUBSTR(content, 1, 50) || '...' as title,
                'note' as type,
                '' as tags,
                created_at
            FROM engagement_notes
            WHERE engagement_id = ?
        ''', (self.engagement_id,))

        for row in cursor.fetchall():
            node = dict(row)
            # Create unique ID combining type and database ID
            node['unique_id'] = f"{node['node_type']}_{node['id']}"
            node['host_ids'] = []
            nodes.append(node)

        # Get all host credentials as nodes
        cursor.execute('''
            SELECT
                'credential' as node_type,
                hc.id,
                COALESCE(hc.username, 'credential') as title,  -- never the secret (M-9)
                'credential' as type,
                '' as tags,
                hc.created_at,
                hc.host_id
            FROM host_credentials hc
            JOIN hosts h ON hc.host_id = h.id
            WHERE h.engagement_id = ?
        ''', (self.engagement_id,))

        for row in cursor.fetchall():
            node = dict(row)
            # Create unique ID combining type and database ID
            node['unique_id'] = f"{node['node_type']}_{node['id']}"
            node['host_ids'] = [node['host_id']] if node.get('host_id') else []
            nodes.append(node)

        # Get all engagement credentials as nodes (General section)
        cursor.execute('''
            SELECT
                'credential' as node_type,
                id,
                COALESCE(username, 'credential') as title,  -- never the secret (M-9)
                'credential' as type,
                '' as tags,
                created_at
            FROM engagement_credentials
            WHERE engagement_id = ?
        ''', (self.engagement_id,))

        for row in cursor.fetchall():
            node = dict(row)
            # Create unique ID combining type and database ID
            node['unique_id'] = f"{node['node_type']}_{node['id']}"
            node['host_ids'] = []
            nodes.append(node)

        # Sort all nodes by creation date
        nodes.sort(key=lambda x: x['created_at'], reverse=True)

        # Get all relationships (edges)
        edges = self.find_all(order_by='created_at DESC')

        logger.debug(f"Graph data: {len(nodes)} nodes ({sum(1 for n in nodes if n.get('node_type') == 'evidence')} evidence, {sum(1 for n in nodes if n.get('node_type') == 'finding')} findings, {sum(1 for n in nodes if n.get('node_type') == 'note')} notes, {sum(1 for n in nodes if n.get('node_type') == 'credential')} credentials), {len(edges)} edges")
        return {
            'nodes': nodes,
            'edges': edges
        }

    def delete_by_node(self, node_type: str, node_id: int) -> int:
        """Delete all relationships involving a node.

        Args:
            node_type: Type of node (evidence, finding, note, credential)
            node_id: Node ID

        Returns:
            Number of relationships deleted
        """
        cursor = self.db.cursor()
        cursor.execute('''
            DELETE FROM node_relationships
            WHERE ((source_node_type = ? AND source_node_id = ?)
               OR (target_node_type = ? AND target_node_id = ?))
            AND engagement_id = ?
        ''', (node_type, node_id, node_type, node_id, self.engagement_id))
        self.db.commit()

        count = cursor.rowcount
        logger.info(f"Deleted {count} relationships for {node_type} {node_id}")
        return count

    def get_relationship_statistics(self) -> Dict:
        """Get statistics about relationships in the current engagement.

        Returns:
            Dictionary with relationship counts by type
        """
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT relationship_type, COUNT(*) as count
            FROM node_relationships
            WHERE engagement_id = ?
            GROUP BY relationship_type
        ''', (self.engagement_id,))

        stats = {row[0]: row[1] for row in cursor.fetchall()}
        stats['total'] = sum(stats.values())
        return stats


class AttackPathDAO(BaseDAO):
    """DAO for saved attack paths."""

    def __init__(self):
        """Initialize AttackPathDAO."""
        super().__init__('attack_paths', engagement_scoped=True)

    def save_path(self, name: str, start_id: int, end_id: int,
                  path_data: List[Dict], description: str = None,
                  created_by: int = None) -> int:
        """Save an attack path.

        Args:
            name: Path name
            start_id: Starting evidence ID
            end_id: Target evidence ID
            path_data: List of evidence items in the path
            description: Optional description
            created_by: User ID who created the path

        Returns:
            int: ID of saved path
        """
        import json

        data = {
            'name': name,
            'description': description,
            'start_evidence_id': start_id,
            'end_evidence_id': end_id,
            'path_json': json.dumps(path_data),
            'created_by': created_by
        }

        path_id = self.create(data)
        logger.info(f"Saved attack path '{name}' with {len(path_data)} steps")
        return path_id

    def get_path(self, path_id: int) -> Optional[Dict]:
        """Get saved attack path with parsed JSON.

        Args:
            path_id: Path ID

        Returns:
            Path dictionary with parsed path_data, or None if not found
        """
        import json

        path = self.find_by_id(path_id)
        if path and path.get('path_json'):
            path['path_data'] = json.loads(path['path_json'])
        return path

    def list_paths(self) -> List[Dict]:
        """List all saved attack paths for the current engagement.

        Returns:
            List of path dictionaries (without full path_json)
        """
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT id, name, description, start_evidence_id, end_evidence_id,
                   created_at, created_by
            FROM attack_paths
            WHERE engagement_id = ?
            ORDER BY created_at DESC
        ''', (self.engagement_id,))

        return [dict(row) for row in cursor.fetchall()]

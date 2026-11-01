"""Evidence Data Access Object.

Handles all database operations for evidence (notes, screenshots, tool output, etc.).
"""

import logging
from typing import Optional, List, Dict, Any
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class EvidenceDAO(BaseDAO):
    """DAO for evidence management operations.

    Provides methods for creating, reading, updating, and deleting evidence,
    as well as specialized queries for search, filtering, and tagging.
    """

    def __init__(self):
        """Initialize EvidenceDAO with engagement-based scoping."""
        super().__init__('evidence', engagement_scoped=True)

    def find_by_type(self, evidence_type: str) -> List[Dict[str, Any]]:
        """Find all evidence of a specific type.

        Args:
            evidence_type: One of 'note', 'command_output', 'screenshot',
                          'tool_output', 'other'

        Returns:
            List of evidence dictionaries
        """
        return self.find_all({'evidence_type': evidence_type},
                           order_by='created_at DESC')

    def find_by_host(self, host_id: int) -> List[Dict[str, Any]]:
        """Find all evidence linked to a specific host.

        Args:
            host_id: Host ID

        Returns:
            List of evidence dictionaries
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT e.* FROM evidence e
            JOIN evidence_hosts eh ON e.id = eh.evidence_id
            WHERE eh.host_id = ? AND e.engagement_id = ?
            ORDER BY e.created_at DESC
        ''', (host_id, self.engagement_id))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def find_without_hosts(self) -> List[Dict[str, Any]]:
        """Find evidence not linked to any host (General section).

        Returns:
            List of evidence dictionaries
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT e.* FROM evidence e
            WHERE e.engagement_id = ?
            AND NOT EXISTS (
                SELECT 1 FROM evidence_hosts eh WHERE eh.evidence_id = e.id
            )
            ORDER BY e.created_at DESC
        ''', (self.engagement_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count_without_hosts(self) -> int:
        """Count evidence not linked to any host.

        Returns:
            int: Count of evidence items in General section
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM evidence e
            WHERE e.engagement_id = ?
            AND NOT EXISTS (
                SELECT 1 FROM evidence_hosts eh WHERE eh.evidence_id = e.id
            )
        ''', (self.engagement_id,))

        return cursor.fetchone()[0]

    def find_by_tags(self, tags: List[str], match_all: bool = False) -> List[Dict[str, Any]]:
        """Find evidence by tags.

        Args:
            tags: List of tag names to search for
            match_all: If True, evidence must have ALL tags (AND).
                      If False, evidence must have ANY tag (OR).

        Returns:
            List of evidence dictionaries
        """
        if not tags:
            return []

        cursor = self.db.cursor()

        if match_all:
            # AND logic - must have all tags
            placeholders = ','.join('?' * len(tags))
            cursor.execute(f'''
                SELECT DISTINCT e.*
                FROM evidence e
                JOIN evidence_tags et ON e.id = et.evidence_id
                JOIN tags t ON et.tag_id = t.id
                WHERE e.engagement_id = ?
                  AND t.name IN ({placeholders})
                GROUP BY e.id
                HAVING COUNT(DISTINCT t.id) = ?
                ORDER BY e.created_at DESC
            ''', (self.engagement_id, *tags, len(tags)))
        else:
            # OR logic - must have at least one tag
            placeholders = ','.join('?' * len(tags))
            cursor.execute(f'''
                SELECT DISTINCT e.*
                FROM evidence e
                JOIN evidence_tags et ON e.id = et.evidence_id
                JOIN tags t ON et.tag_id = t.id
                WHERE e.engagement_id = ?
                  AND t.name IN ({placeholders})
                ORDER BY e.created_at DESC
            ''', (self.engagement_id, *tags))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def search_fulltext(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search across evidence using FTS4.

        Args:
            query: Search query
            limit: Maximum number of results (max 500)

        Returns:
            List of evidence dictionaries, ordered by relevance
        """
        cursor = self.db.cursor()
        limit = min(limit, 500)

        # FTS4 search
        cursor.execute('''
            SELECT e.*
            FROM evidence e
            JOIN evidence_fts fts ON e.id = fts.docid
            WHERE e.engagement_id = ? AND fts.evidence_fts MATCH ?
            LIMIT ?
        ''', (self.engagement_id, query, limit))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def filter_evidence(self,
                       evidence_type: Optional[str] = None,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       tags: Optional[List[str]] = None,
                       tool: Optional[str] = None,
                       severity: Optional[str] = None,
                       limit: int = 50,
                       offset: int = 0) -> Dict[str, Any]:
        """Advanced filtering with dynamic query builder.

        Args:
            evidence_type: Filter by evidence type
            date_from: Filter by created_at >= date_from (ISO format)
            date_to: Filter by created_at <= date_to (ISO format)
            tags: Filter by tags (AND logic)
            tool: Filter by tool_name (generated column)
            severity: Filter by severity_level (generated column)
            limit: Maximum results (max 500)
            offset: Pagination offset

        Returns:
            Dictionary with 'results', 'count', 'total', 'offset'
        """
        cursor = self.db.cursor()
        limit = min(limit, 500)

        # Build query dynamically
        base_query = 'SELECT DISTINCT e.*'
        from_clause = ' FROM evidence e'
        where_clauses = ['e.engagement_id = ?']
        params = [self.engagement_id]

        # Type filter
        if evidence_type:
            where_clauses.append('e.evidence_type = ?')
            params.append(evidence_type)

        # Date range filters
        if date_from:
            where_clauses.append('e.created_at >= ?')
            params.append(date_from)
        if date_to:
            where_clauses.append('e.created_at <= ?')
            params.append(date_to)

        # Tool filter (generated column)
        if tool:
            where_clauses.append('e.tool_name = ?')
            params.append(tool)

        # Severity filter (generated column)
        if severity:
            where_clauses.append('e.severity_level = ?')
            params.append(severity)

        # Tag filter (AND logic)
        group_by = ''
        having_clause = ''
        if tags:
            tags = [t.strip() for t in tags if t.strip()]
            if tags:
                from_clause += '''
                    JOIN evidence_tags et ON e.id = et.evidence_id
                    JOIN tags t ON et.tag_id = t.id
                '''
                placeholders = ','.join('?' * len(tags))
                where_clauses.append(f't.name IN ({placeholders})')
                params.extend(tags)
                group_by = ' GROUP BY e.id'
                having_clause = f' HAVING COUNT(DISTINCT t.id) = {len(tags)}'

        # Build final query
        where_sql = ' WHERE ' + ' AND '.join(where_clauses)
        order_by = ' ORDER BY e.created_at DESC'
        pagination = ' LIMIT ? OFFSET ?'

        query = base_query + from_clause + where_sql + group_by + having_clause + order_by + pagination
        params.extend([limit, offset])

        cursor.execute(query, params)
        results = [self._row_to_dict(row) for row in cursor.fetchall()]

        # Get total count
        count_query = f'SELECT COUNT(DISTINCT e.id){from_clause}{where_sql}{group_by}{having_clause}'
        cursor.execute(count_query, params[:-2])  # Exclude limit/offset

        count_rows = cursor.fetchall()
        if group_by:
            total = len(count_rows)
        else:
            total = count_rows[0][0] if count_rows else 0

        return {
            'results': results,
            'count': len(results),
            'total': total,
            'offset': offset
        }

    def link_to_host(self, evidence_id: int, host_id: int, source: str = 'manual') -> bool:
        """Link evidence to a host.

        Args:
            evidence_id: Evidence ID
            host_id: Host ID
            source: Source of the link ('manual', 'parser', etc.)

        Returns:
            bool: True if linked, False if already linked or error
        """
        cursor = self.db.cursor()

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO evidence_hosts (evidence_id, host_id, source)
                VALUES (?, ?, ?)
            ''', (evidence_id, host_id, source))
            self.db.commit()

            linked = cursor.rowcount > 0
            if linked:
                logger.info(f"Linked evidence {evidence_id} to host {host_id}")
            return linked
        except Exception as e:
            logger.error(f"Failed to link evidence {evidence_id} to host {host_id}: {e}")
            self.db.rollback()
            return False

    def unlink_from_host(self, evidence_id: int, host_id: int) -> bool:
        """Unlink evidence from a host.

        Args:
            evidence_id: Evidence ID
            host_id: Host ID

        Returns:
            bool: True if unlinked, False if not found
        """
        cursor = self.db.cursor()

        cursor.execute('''
            DELETE FROM evidence_hosts
            WHERE evidence_id = ? AND host_id = ?
        ''', (evidence_id, host_id))
        self.db.commit()

        unlinked = cursor.rowcount > 0
        if unlinked:
            logger.info(f"Unlinked evidence {evidence_id} from host {host_id}")
        return unlinked

    def unlink_all_hosts(self, evidence_id: int) -> int:
        """Unlink evidence from all hosts.

        Args:
            evidence_id: Evidence ID

        Returns:
            int: Number of hosts unlinked
        """
        cursor = self.db.cursor()

        cursor.execute('''
            DELETE FROM evidence_hosts WHERE evidence_id = ?
        ''', (evidence_id,))
        self.db.commit()

        count = cursor.rowcount
        logger.info(f"Unlinked evidence {evidence_id} from {count} hosts")
        return count

    def get_linked_hosts(self, evidence_id: int) -> List[Dict[str, Any]]:
        """Get all hosts linked to an evidence item.

        Args:
            evidence_id: Evidence ID

        Returns:
            List of host dictionaries with 'link_source' added
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT h.*, eh.source as link_source
            FROM hosts h
            JOIN evidence_hosts eh ON h.id = eh.host_id
            WHERE eh.evidence_id = ?
            ORDER BY h.ip
        ''', (evidence_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def bulk_tag(self, evidence_ids: List[int], tags: str) -> int:
        """Append tags to multiple evidence items.

        Args:
            evidence_ids: List of evidence IDs
            tags: Comma-separated tags to append

        Returns:
            int: Number of items tagged
        """
        if not evidence_ids or not tags:
            return 0

        cursor = self.db.cursor()
        count = 0

        for evidence_id in evidence_ids:
            # Get existing tags
            cursor.execute("SELECT tags FROM evidence WHERE id = ?", (evidence_id,))
            row = cursor.fetchone()
            if not row:
                continue

            existing_tags = row[0] if row[0] else ''

            # Merge tags
            if existing_tags:
                merged_tags = f"{existing_tags},{tags}"
            else:
                merged_tags = tags

            # Update evidence
            cursor.execute('''
                UPDATE evidence
                SET tags = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (merged_tags, evidence_id))
            count += 1

        self.db.commit()
        logger.info(f"Tagged {count} evidence items")
        return count

    def bulk_delete(self, evidence_ids: List[int]) -> int:
        """Delete multiple evidence items.

        Args:
            evidence_ids: List of evidence IDs

        Returns:
            int: Number of items deleted
        """
        if not evidence_ids:
            return 0

        cursor = self.db.cursor()

        placeholders = ','.join('?' * len(evidence_ids))
        cursor.execute(f'''
            DELETE FROM evidence
            WHERE id IN ({placeholders}) AND engagement_id = ?
        ''', (*evidence_ids, self.engagement_id))
        self.db.commit()

        count = cursor.rowcount
        logger.info(f"Deleted {count} evidence items")
        return count

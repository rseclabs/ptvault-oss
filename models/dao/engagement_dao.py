"""Engagement Data Access Object.

Handles all database operations for engagements (client projects/pentests).
"""

import logging
from typing import Optional, List, Dict, Any
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class EngagementDAO(BaseDAO):
    """DAO for engagement management operations.

    Provides methods for creating, reading, updating, and deleting engagements,
    as well as specialized queries for engagement statistics and export data.
    """

    def __init__(self):
        """Initialize EngagementDAO.

        Note: Engagements are NOT engagement-scoped (they define the scope).
        """
        super().__init__('engagements', engagement_scoped=False)

    def find_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Find all engagements with given status.

        Args:
            status: One of 'active', 'completed', 'archived'

        Returns:
            List of engagement dictionaries
        """
        return self.find_all({'status': status}, order_by='created_at DESC')

    def find_active_engagements(self) -> List[Dict[str, Any]]:
        """Find all active engagements.

        Returns:
            List of engagement dictionaries with status='active'
        """
        return self.find_by_status('active')

    def get_statistics(self, engagement_id: int) -> Dict[str, Any]:
        """Get statistics for an engagement.

        Args:
            engagement_id: Engagement ID

        Returns:
            Dictionary with counts of evidence, hosts, findings, etc.
        """
        cursor = self.db.cursor()

        stats = {}

        # Count evidence
        cursor.execute(
            'SELECT COUNT(*) FROM evidence WHERE engagement_id = ?',
            (engagement_id,)
        )
        stats['evidence_count'] = cursor.fetchone()[0]

        # Count evidence by type
        cursor.execute('''
            SELECT evidence_type, COUNT(*)
            FROM evidence
            WHERE engagement_id = ?
            GROUP BY evidence_type
        ''', (engagement_id,))
        stats['evidence_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Count evidence by tool (using generated column)
        cursor.execute('''
            SELECT tool_name, COUNT(*)
            FROM evidence
            WHERE engagement_id = ? AND tool_name IS NOT NULL
            GROUP BY tool_name
        ''', (engagement_id,))
        stats['evidence_by_tool'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Count evidence by severity (using generated column)
        cursor.execute('''
            SELECT severity_level, COUNT(*)
            FROM evidence
            WHERE engagement_id = ? AND severity_level IS NOT NULL
            GROUP BY severity_level
        ''', (engagement_id,))
        stats['evidence_by_severity'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Count hosts
        cursor.execute(
            'SELECT COUNT(*) FROM hosts WHERE engagement_id = ?',
            (engagement_id,)
        )
        stats['host_count'] = cursor.fetchone()[0]

        # Count findings
        cursor.execute(
            'SELECT COUNT(*) FROM engagement_findings WHERE engagement_id = ?',
            (engagement_id,)
        )
        stats['findings_count'] = cursor.fetchone()[0]

        # Count unique tags
        cursor.execute('''
            SELECT COUNT(DISTINCT t.id)
            FROM tags t
            JOIN evidence_tags et ON t.id = et.tag_id
            JOIN evidence e ON et.evidence_id = e.id
            WHERE e.engagement_id = ?
        ''', (engagement_id,))
        stats['unique_tags'] = cursor.fetchone()[0]

        # Count files with attachments
        cursor.execute('''
            SELECT COUNT(*)
            FROM evidence
            WHERE engagement_id = ? AND file_path IS NOT NULL
        ''', (engagement_id,))
        stats['files_count'] = cursor.fetchone()[0]

        logger.debug(f"Got statistics for engagement {engagement_id}: {stats}")
        return stats

    def get_export_data(self, engagement_id: int) -> Dict[str, Any]:
        """Get complete engagement data for export.

        Includes engagement details, evidence, hosts, ports, credentials,
        notes, and all related data in a structured format.

        Args:
            engagement_id: Engagement ID

        Returns:
            Dictionary with complete engagement data

        Raises:
            ValueError: If engagement not found
        """
        cursor = self.db.cursor()

        # Load engagement
        engagement = self.find_by_id(engagement_id)
        if not engagement:
            raise ValueError('Engagement not found')

        # Load all evidence with tags
        cursor.execute('''
            SELECT
                e.id, e.engagement_id, e.evidence_type, e.title, e.content,
                e.tags, e.file_path, e.file_name, e.file_size, e.metadata,
                e.created_at, e.updated_at,
                e.tool_name, e.severity_level,
                GROUP_CONCAT(t.name, ',') as tag_names
            FROM evidence e
            LEFT JOIN evidence_tags et ON e.id = et.evidence_id
            LEFT JOIN tags t ON et.tag_id = t.id
            WHERE e.engagement_id = ?
            GROUP BY e.id
            ORDER BY e.created_at DESC
        ''', (engagement_id,))

        evidence_list = []
        for row in cursor.fetchall():
            import json

            # Parse tags
            tag_names = row[14]
            tags = tag_names.split(',') if tag_names else []

            # Parse metadata JSON
            metadata_json = None
            if row[9]:
                try:
                    metadata_json = json.loads(row[9])
                except (json.JSONDecodeError, ValueError):
                    metadata_json = None

            evidence_list.append({
                'id': row[0],
                'engagement_id': row[1],
                'evidence_type': row[2],
                'title': row[3],
                'content': row[4],
                'tags': tags,
                'file_path': row[6],
                'file_name': row[7],
                'file_size': row[8],
                'metadata': metadata_json,
                'created_at': row[10],
                'updated_at': row[11],
                'tool_name': row[12],
                'severity_level': row[13]
            })

        # Load hosts
        cursor.execute('''
            SELECT id, engagement_id, ip, hostname, os, notes, rooted, shell,
                   interested, not_interested, out_of_scope, flagged, reviewed,
                   color_category, created_at, updated_at
            FROM hosts
            WHERE engagement_id = ?
            ORDER BY ip
        ''', (engagement_id,))

        hosts_list = []
        host_ids = []
        for row in cursor.fetchall():
            host_id = row[0]
            host_ids.append(host_id)
            hosts_list.append({
                'id': host_id,
                'engagement_id': row[1],
                'ip': row[2],
                'hostname': row[3],
                'os': row[4],
                'notes': row[5],
                'rooted': row[6],
                'has_shell': row[7],
                'interested': row[8],
                'not_interested': row[9],
                'out_of_scope': row[10],
                'flagged': row[11],
                'reviewed': row[12],
                'color_category': row[13],
                'created_at': row[14],
                'updated_at': row[15]
            })

        # Load related tables only if we have hosts
        host_notes_list = []
        host_ports_list = []
        host_credentials_list = []
        evidence_hosts_list = []

        if host_ids:
            placeholders = ','.join('?' * len(host_ids))

            # Host notes
            cursor.execute(f'''
                SELECT id, host_id, content, created_at, updated_at
                FROM host_notes
                WHERE host_id IN ({placeholders})
            ''', host_ids)
            for row in cursor.fetchall():
                host_notes_list.append({
                    'id': row[0],
                    'host_id': row[1],
                    'content': row[2],
                    'created_at': row[3],
                    'updated_at': row[4]
                })

            # Host ports
            cursor.execute(f'''
                SELECT id, host_id, port, protocol, state, service, version,
                       source, evidence_id, created_at, updated_at
                FROM host_ports
                WHERE host_id IN ({placeholders})
            ''', host_ids)
            for row in cursor.fetchall():
                host_ports_list.append({
                    'id': row[0],
                    'host_id': row[1],
                    'port': row[2],
                    'protocol': row[3],
                    'state': row[4],
                    'service': row[5],
                    'version': row[6],
                    'source': row[7],
                    'evidence_id': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                })

            # Host credentials
            cursor.execute(f'''
                SELECT id, host_id, username, password, password_type, hash_type,
                       service, notes, created_at, updated_at
                FROM host_credentials
                WHERE host_id IN ({placeholders})
            ''', host_ids)
            for row in cursor.fetchall():
                host_credentials_list.append({
                    'id': row[0],
                    'host_id': row[1],
                    'username': row[2],
                    'password': row[3],
                    'password_type': row[4],
                    'hash_type': row[5],
                    'service': row[6],
                    'notes': row[7],
                    'created_at': row[8],
                    'updated_at': row[9]
                })

            # Evidence-hosts junction
            cursor.execute(f'''
                SELECT evidence_id, host_id, source
                FROM evidence_hosts
                WHERE host_id IN ({placeholders})
            ''', host_ids)
            for row in cursor.fetchall():
                evidence_hosts_list.append({
                    'evidence_id': row[0],
                    'host_id': row[1],
                    'source': row[2]
                })

        # Load engagement-level tables
        cursor.execute('''
            SELECT id, engagement_id, content, created_at, updated_at
            FROM engagement_notes
            WHERE engagement_id = ?
        ''', (engagement_id,))
        engagement_notes_list = [
            {'id': r[0], 'engagement_id': r[1], 'content': r[2],
             'created_at': r[3], 'updated_at': r[4]}
            for r in cursor.fetchall()
        ]

        cursor.execute('''
            SELECT id, engagement_id, username, password_or_hash,
                   credential_type, description, created_at, updated_at
            FROM engagement_credentials
            WHERE engagement_id = ?
        ''', (engagement_id,))
        engagement_credentials_list = [
            {'id': r[0], 'engagement_id': r[1], 'username': r[2],
             'password_or_hash': r[3], 'credential_type': r[4],
             'description': r[5], 'created_at': r[6], 'updated_at': r[7]}
            for r in cursor.fetchall()
        ]

        cursor.execute('''
            SELECT id, engagement_id, title, content, session_datetime,
                   created_at, updated_at
            FROM terminal_dumps
            WHERE engagement_id = ?
        ''', (engagement_id,))
        terminal_dumps_list = [
            {'id': r[0], 'engagement_id': r[1], 'title': r[2],
             'content': r[3], 'session_datetime': r[4],
             'created_at': r[5], 'updated_at': r[6]}
            for r in cursor.fetchall()
        ]

        cursor.execute('''
            SELECT id, engagement_id, title, ip_address, hostname,
                   criticality, cvss_score, finding_content,
                   remediation_content, include_in_report,
                   created_at, updated_at
            FROM engagement_findings
            WHERE engagement_id = ?
        ''', (engagement_id,))
        engagement_findings_list = [
            {'id': r[0], 'engagement_id': r[1], 'title': r[2],
             'ip_address': r[3], 'hostname': r[4], 'criticality': r[5],
             'cvss_score': r[6], 'finding_content': r[7],
             'remediation_content': r[8], 'include_in_report': r[9],
             'created_at': r[10], 'updated_at': r[11]}
            for r in cursor.fetchall()
        ]

        # Get statistics
        statistics = self.get_statistics(engagement_id)

        # Build complete export data
        from datetime import datetime
        return {
            'engagement': engagement,
            'evidence': evidence_list,
            'hosts': hosts_list,
            'host_notes': host_notes_list,
            'host_ports': host_ports_list,
            'host_credentials': host_credentials_list,
            'evidence_hosts': evidence_hosts_list,
            'engagement_notes': engagement_notes_list,
            'engagement_credentials': engagement_credentials_list,
            'terminal_dumps': terminal_dumps_list,
            'engagement_findings': engagement_findings_list,
            'statistics': statistics,
            'export_metadata': {
                'exported_at': datetime.utcnow().isoformat(),
                'ptvault_version': '1.0.0',
                'format_version': '2.0'
            }
        }

    def delete_with_cascade(self, engagement_id: int) -> bool:
        """Delete engagement and ALL associated data.

        This includes: hosts, evidence, notes, ports, credentials, findings.

        Args:
            engagement_id: Engagement ID

        Returns:
            bool: True if deleted, False if not found
        """
        cursor = self.db.cursor()

        # Check if engagement exists
        if not self.exists({'id': engagement_id}):
            return False

        # Every engagement-scoped table (M-13); see models/engagement_cleanup.py
        from models.engagement_cleanup import delete_engagement
        delete_engagement(cursor, engagement_id)

        self.db.commit()

        logger.info(f"Deleted engagement {engagement_id} with cascade")
        return True

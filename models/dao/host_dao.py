"""Host Data Access Object.

Handles all database operations for hosts and related entities (ports, credentials, notes).
"""

import logging
from typing import Optional, List, Dict, Any
from models.dao.base import BaseDAO

logger = logging.getLogger(__name__)


class HostDAO(BaseDAO):
    """DAO for host management operations.

    Provides methods for managing hosts, ports, credentials, and notes.
    """

    def __init__(self):
        """Initialize HostDAO with engagement-based scoping."""
        super().__init__('hosts', engagement_scoped=True)

    def find_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Find host by IP address.

        Args:
            ip: IP address

        Returns:
            Host dictionary or None if not found
        """
        return self.find_one({'ip': ip})

    def find_by_indicator(self, indicator: str, value: bool = True) -> List[Dict[str, Any]]:
        """Find hosts by indicator flag.

        Args:
            indicator: One of 'rooted', 'shell', 'interested', 'not_interested',
                      'out_of_scope', 'flagged', 'reviewed'
            value: True to find hosts with indicator set, False for unset

        Returns:
            List of host dictionaries
        """
        return self.find_all({indicator: 1 if value else 0}, order_by='ip')

    def find_by_color(self, color: str) -> List[Dict[str, Any]]:
        """Find hosts by color category.

        Args:
            color: Color name (e.g., 'red', 'green', 'blue')

        Returns:
            List of host dictionaries
        """
        return self.find_all({'color_category': color}, order_by='ip')

    def get_with_evidence_count(self) -> List[Dict[str, Any]]:
        """Get all hosts with evidence count.

        Returns:
            List of host dictionaries with 'evidence_count' field added
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT
                h.*,
                COUNT(DISTINCT eh.evidence_id) as evidence_count
            FROM hosts h
            LEFT JOIN evidence_hosts eh ON h.id = eh.host_id
            WHERE h.engagement_id = ?
            GROUP BY h.id
            ORDER BY h.ip
        ''', (self.engagement_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_full_details(self, host_id: int) -> Optional[Dict[str, Any]]:
        """Get host with all related data (evidence, ports, credentials, notes).

        Args:
            host_id: Host ID

        Returns:
            Dictionary with host data and nested lists for related entities
        """
        host = self.find_by_id(host_id)
        if not host:
            return None

        cursor = self.db.cursor()

        # Get linked evidence
        cursor.execute('''
            SELECT
                e.id, e.evidence_type, e.title, e.content,
                e.file_name, e.created_at, e.tool_name, e.severity_level,
                eh.source
            FROM evidence e
            JOIN evidence_hosts eh ON e.id = eh.evidence_id
            WHERE eh.host_id = ?
            ORDER BY e.created_at DESC
        ''', (host_id,))

        evidence = []
        for row in cursor.fetchall():
            evidence.append({
                'id': row[0],
                'evidence_type': row[1],
                'title': row[2],
                'content': row[3],
                'file_name': row[4],
                'created_at': row[5],
                'tool_name': row[6],
                'severity_level': row[7],
                'link_source': row[8]
            })

        # Get ports
        cursor.execute('''
            SELECT id, port, protocol, state, service, version, source, created_at
            FROM host_ports
            WHERE host_id = ?
            ORDER BY port ASC
        ''', (host_id,))

        ports = []
        for row in cursor.fetchall():
            ports.append({
                'id': row[0],
                'port': row[1],
                'protocol': row[2],
                'state': row[3],
                'service': row[4],
                'version': row[5],
                'source': row[6],
                'created_at': row[7]
            })

        # Get credentials
        cursor.execute('''
            SELECT id, username, password, password_type, hash_type,
                   service, notes, created_at
            FROM host_credentials
            WHERE host_id = ?
            ORDER BY created_at DESC
        ''', (host_id,))

        credentials = []
        for row in cursor.fetchall():
            credentials.append({
                'id': row[0],
                'username': row[1],
                'password': row[2],
                'password_type': row[3],
                'hash_type': row[4],
                'service': row[5],
                'notes': row[6],
                'created_at': row[7]
            })

        # Get notes
        cursor.execute('''
            SELECT id, content, created_at, updated_at
            FROM host_notes
            WHERE host_id = ?
            ORDER BY created_at DESC
        ''', (host_id,))

        notes = []
        for row in cursor.fetchall():
            notes.append({
                'id': row[0],
                'content': row[1],
                'created_at': row[2],
                'updated_at': row[3]
            })

        # Build complete host object
        host['evidence'] = evidence
        host['evidence_count'] = len(evidence)
        host['ports'] = ports
        host['credentials'] = credentials
        host['notes'] = notes

        return host

    # Port management methods

    def add_port(self, host_id: int, port: int, protocol: str = 'tcp',
                 state: str = 'open', service: Optional[str] = None,
                 version: Optional[str] = None, source: str = 'manual',
                 evidence_id: Optional[int] = None) -> int:
        """Add port to a host.

        Args:
            host_id: Host ID
            port: Port number
            protocol: Protocol (tcp/udp)
            state: Port state (open/closed/filtered)
            service: Service name
            version: Service version
            source: Source of discovery
            evidence_id: Related evidence ID

        Returns:
            int: Port record ID

        Raises:
            sqlite3.IntegrityError: If port already exists for this host
        """
        cursor = self.db.cursor()

        cursor.execute('''
            INSERT INTO host_ports
            (host_id, port, protocol, state, service, version, source, evidence_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (host_id, port, protocol, state, service, version, source, evidence_id))
        self.db.commit()

        logger.info(f"Added port {port}/{protocol} to host {host_id}")
        return cursor.lastrowid

    def update_port(self, port_id: int, data: Dict[str, Any]) -> bool:
        """Update port details.

        Args:
            port_id: Port record ID
            data: Dictionary of fields to update

        Returns:
            bool: True if updated
        """
        if not data:
            return False

        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        values = list(data.values())
        values.append(port_id)

        cursor = self.db.cursor()
        cursor.execute(f'''
            UPDATE host_ports
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', values)
        self.db.commit()

        logger.info(f"Updated port {port_id}")
        return cursor.rowcount > 0

    def delete_port(self, port_id: int) -> bool:
        """Delete a port.

        Args:
            port_id: Port record ID

        Returns:
            bool: True if deleted
        """
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM host_ports WHERE id = ?', (port_id,))
        self.db.commit()

        logger.info(f"Deleted port {port_id}")
        return cursor.rowcount > 0

    def get_ports(self, host_id: int) -> List[Dict[str, Any]]:
        """Get all ports for a host.

        Args:
            host_id: Host ID

        Returns:
            List of port dictionaries
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT id, host_id, port, protocol, state, service, version,
                   source, evidence_id, created_at, updated_at
            FROM host_ports
            WHERE host_id = ?
            ORDER BY port ASC
        ''', (host_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_port_grid_data(self) -> Dict[str, Any]:
        """Get all hosts and ports for port grid visualization.

        Returns:
            Dictionary with 'hosts' and 'ports' lists
        """
        cursor = self.db.cursor()

        # Get all hosts
        cursor.execute('''
            SELECT id, ip, hostname
            FROM hosts
            WHERE engagement_id = ?
            ORDER BY ip ASC
        ''', (self.engagement_id,))

        hosts = []
        host_ids = []
        for row in cursor.fetchall():
            hosts.append({
                'id': row[0],
                'ip': row[1],
                'hostname': row[2]
            })
            host_ids.append(row[0])

        if not host_ids:
            return {'hosts': [], 'ports': []}

        # Get all ports for all hosts
        placeholders = ','.join('?' * len(host_ids))
        cursor.execute(f'''
            SELECT host_id, port, protocol, state, service
            FROM host_ports
            WHERE host_id IN ({placeholders})
            ORDER BY port ASC
        ''', host_ids)

        # Build port map: port/protocol -> {port, protocol, service, hosts: {hostId: state}}
        port_map = {}
        for row in cursor.fetchall():
            host_id, port, protocol, state, service = row
            port_key = f"{port}/{protocol}"

            if port_key not in port_map:
                port_map[port_key] = {
                    'port': port,
                    'protocol': protocol,
                    'service': service or '',
                    'hosts': {}
                }

            port_map[port_key]['hosts'][host_id] = state

            # Update service name if we have a better one
            if service and not port_map[port_key]['service']:
                port_map[port_key]['service'] = service

        # Sort ports by port number
        sorted_ports = sorted(port_map.values(), key=lambda p: p['port'])

        return {
            'hosts': hosts,
            'ports': sorted_ports
        }

    # Credential management methods

    def add_credential(self, host_id: int, username: Optional[str] = None,
                      password: Optional[str] = None, password_type: str = 'cleartext',
                      hash_type: Optional[str] = None, service: Optional[str] = None,
                      notes: Optional[str] = None) -> int:
        """Add credential to a host.

        Args:
            host_id: Host ID
            username: Username
            password: Password or hash
            password_type: Type ('cleartext' or 'hash')
            hash_type: Hash type if password_type='hash'
            service: Service name
            notes: Additional notes

        Returns:
            int: Credential record ID
        """
        cursor = self.db.cursor()

        cursor.execute('''
            INSERT INTO host_credentials
            (host_id, username, password, password_type, hash_type, service, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (host_id, username, password, password_type, hash_type, service, notes))
        self.db.commit()

        logger.info(f"Added credential for host {host_id}")
        return cursor.lastrowid

    def update_credential(self, credential_id: int, data: Dict[str, Any]) -> bool:
        """Update credential details.

        Args:
            credential_id: Credential record ID
            data: Dictionary of fields to update

        Returns:
            bool: True if updated
        """
        if not data:
            return False

        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        values = list(data.values())
        values.append(credential_id)

        cursor = self.db.cursor()
        cursor.execute(f'''
            UPDATE host_credentials
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', values)
        self.db.commit()

        logger.info(f"Updated credential {credential_id}")
        return cursor.rowcount > 0

    def delete_credential(self, credential_id: int) -> bool:
        """Delete a credential.

        Args:
            credential_id: Credential record ID

        Returns:
            bool: True if deleted
        """
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM host_credentials WHERE id = ?', (credential_id,))
        self.db.commit()

        logger.info(f"Deleted credential {credential_id}")
        return cursor.rowcount > 0

    def get_credentials(self, host_id: int) -> List[Dict[str, Any]]:
        """Get all credentials for a host.

        Args:
            host_id: Host ID

        Returns:
            List of credential dictionaries
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT id, host_id, username, password, password_type, hash_type,
                   service, notes, created_at, updated_at
            FROM host_credentials
            WHERE host_id = ?
            ORDER BY created_at DESC
        ''', (host_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

    # Note management methods

    def add_note(self, host_id: int, content: str) -> int:
        """Add note to a host.

        Args:
            host_id: Host ID
            content: Note content

        Returns:
            int: Note record ID
        """
        cursor = self.db.cursor()

        cursor.execute('''
            INSERT INTO host_notes (host_id, content)
            VALUES (?, ?)
        ''', (host_id, content))
        self.db.commit()

        logger.info(f"Added note to host {host_id}")
        return cursor.lastrowid

    def update_note(self, note_id: int, content: str) -> bool:
        """Update note content.

        Args:
            note_id: Note record ID
            content: New note content

        Returns:
            bool: True if updated
        """
        cursor = self.db.cursor()

        cursor.execute('''
            UPDATE host_notes
            SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (content, note_id))
        self.db.commit()

        logger.info(f"Updated note {note_id}")
        return cursor.rowcount > 0

    def delete_note(self, note_id: int) -> bool:
        """Delete a note.

        Args:
            note_id: Note record ID

        Returns:
            bool: True if deleted
        """
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM host_notes WHERE id = ?', (note_id,))
        self.db.commit()

        logger.info(f"Deleted note {note_id}")
        return cursor.rowcount > 0

    def get_notes(self, host_id: int) -> List[Dict[str, Any]]:
        """Get all notes for a host.

        Args:
            host_id: Host ID

        Returns:
            List of note dictionaries
        """
        cursor = self.db.cursor()

        cursor.execute('''
            SELECT id, host_id, content, created_at, updated_at
            FROM host_notes
            WHERE host_id = ?
            ORDER BY created_at DESC
        ''', (host_id,))

        return [self._row_to_dict(row) for row in cursor.fetchall()]

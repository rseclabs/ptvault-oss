"""
Host extraction utilities for PTVault.
Extracts host information from parsed tool metadata and manages host-evidence relationships.
"""

import json
from urllib.parse import urlparse


def extract_hosts_from_metadata(metadata):
    """
    Extract host information from parsed tool metadata.

    Args:
        metadata: Dict containing parsed tool output

    Returns:
        List of dicts with keys: ip, hostname, os
    """
    if not metadata or not isinstance(metadata, dict):
        return []

    hosts = []
    tool = metadata.get('tool', '')

    if tool == 'nmap':
        for host in metadata.get('hosts', []):
            ip = host.get('ip')
            if ip:
                hosts.append({
                    'ip': ip,
                    'hostname': host.get('hostname'),
                    'os': host.get('os')
                })

    elif tool == 'nessus':
        for host in metadata.get('hosts', []):
            ip = host.get('ip')
            if ip:
                hosts.append({
                    'ip': ip,
                    'hostname': host.get('hostname'),
                    'os': host.get('os')
                })

    elif tool == 'burp_suite':
        seen_hosts = set()
        for issue in metadata.get('issues', []):
            host_url = issue.get('host', '')
            if host_url and host_url not in seen_hosts:
                seen_hosts.add(host_url)
                # Parse URL to extract host
                try:
                    if '://' in host_url:
                        parsed = urlparse(host_url)
                        ip = parsed.netloc
                    else:
                        ip = host_url
                    # Remove port if present
                    if ':' in ip:
                        ip = ip.split(':')[0]
                    if ip:
                        hosts.append({
                            'ip': ip,
                            'hostname': None,
                            'os': None
                        })
                except Exception:
                    pass

    return hosts


def get_or_create_host(engagement_id, ip, hostname=None, os_info=None, conn=None):
    """
    Get existing host or create a new one.

    Args:
        engagement_id: The engagement ID
        ip: The IP address or hostname (required)
        hostname: Optional hostname
        os_info: Optional OS information
        conn: Database connection

    Returns:
        Host ID (int) or None if failed
    """
    if not conn or not ip:
        return None

    cursor = conn.cursor()

    try:
        # Check if host already exists
        cursor.execute('''
            SELECT id, hostname, os FROM hosts
            WHERE engagement_id = ? AND ip = ?
        ''', (engagement_id, ip))
        row = cursor.fetchone()

        if row:
            # Host exists - update if we have new info
            host_id = row[0]
            existing_hostname = row[1]
            existing_os = row[2]

            # Only update if we have new info
            new_hostname = hostname if hostname else existing_hostname
            new_os = os_info if os_info else existing_os

            if new_hostname != existing_hostname or new_os != existing_os:
                cursor.execute('''
                    UPDATE hosts
                    SET hostname = ?, os = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_hostname, new_os, host_id))

            return host_id
        else:
            # Insert new host
            cursor.execute('''
                INSERT INTO hosts (engagement_id, ip, hostname, os)
                VALUES (?, ?, ?, ?)
            ''', (engagement_id, ip, hostname, os_info))

            return cursor.lastrowid

    except Exception as e:
        print(f"Error getting/creating host {ip}: {e}")
        return None


def link_evidence_to_host(evidence_id, host_id, source='manual', conn=None):
    """
    Create a link between evidence and a host.

    Args:
        evidence_id: The evidence ID
        host_id: The host ID
        source: 'auto' (from parser) or 'manual' (user-assigned)
        conn: Database connection

    Returns:
        True if successful, False otherwise
    """
    if not conn or not evidence_id or not host_id:
        return False

    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR IGNORE INTO evidence_hosts (evidence_id, host_id, source)
            VALUES (?, ?, ?)
        ''', (evidence_id, host_id, source))
        return True
    except Exception as e:
        print(f"Error linking evidence {evidence_id} to host {host_id}: {e}")
        return False


def unlink_evidence_from_host(evidence_id, host_id, conn=None):
    """
    Remove a link between evidence and a host.

    Args:
        evidence_id: The evidence ID
        host_id: The host ID
        conn: Database connection

    Returns:
        True if successful, False otherwise
    """
    if not conn or not evidence_id or not host_id:
        return False

    cursor = conn.cursor()

    try:
        cursor.execute('''
            DELETE FROM evidence_hosts
            WHERE evidence_id = ? AND host_id = ?
        ''', (evidence_id, host_id))
        return True
    except Exception as e:
        print(f"Error unlinking evidence {evidence_id} from host {host_id}: {e}")
        return False


def extract_ports_from_metadata(metadata, host_ip):
    """
    Extract port information from parsed metadata for a specific host.

    Args:
        metadata: Dict containing parsed tool output
        host_ip: The IP address to extract ports for

    Returns:
        List of dicts with keys: port, protocol, state, service, version, source
    """
    if not metadata or not isinstance(metadata, dict):
        return []

    ports = []
    tool = metadata.get('tool', '')

    if tool == 'nmap':
        for host in metadata.get('hosts', []):
            if host.get('ip') == host_ip:
                for port_data in host.get('open_ports', []):
                    port_num = port_data.get('port')
                    if port_num:
                        product = port_data.get('product', '')
                        version = port_data.get('version', '')
                        version_str = f"{product} {version}".strip() if product or version else None
                        ports.append({
                            'port': port_num,
                            'protocol': port_data.get('protocol', 'tcp'),
                            'state': port_data.get('state', 'open'),
                            'service': port_data.get('service'),
                            'version': version_str,
                            'source': 'nmap'
                        })

    elif tool == 'nessus':
        for host in metadata.get('hosts', []):
            if host.get('ip') == host_ip:
                seen_ports = set()
                for vuln in host.get('vulnerabilities', []):
                    port_num = vuln.get('port')
                    if not port_num or port_num == '0':
                        continue
                    try:
                        port_num = int(port_num)
                    except (ValueError, TypeError):
                        continue

                    protocol = vuln.get('protocol', 'tcp')
                    port_key = (port_num, protocol)
                    if port_key in seen_ports:
                        continue
                    seen_ports.add(port_key)

                    ports.append({
                        'port': port_num,
                        'protocol': protocol,
                        'state': 'open',
                        'service': vuln.get('svc_name') or vuln.get('service'),
                        'version': None,
                        'source': 'nessus'
                    })

    return ports


def insert_ports_for_host(host_id, ports, evidence_id, conn):
    """
    Insert port entries for a host.

    Args:
        host_id: The host ID
        ports: List of port dicts
        evidence_id: The evidence ID (for source tracking)
        conn: Database connection

    Returns:
        Number of ports inserted/updated
    """
    if not conn or not host_id or not ports:
        return 0

    cursor = conn.cursor()
    count = 0

    for port_data in ports:
        try:
            port_num = port_data['port']
            protocol = port_data.get('protocol', 'tcp')
            state = port_data.get('state', 'open')
            service = port_data.get('service')
            version = port_data.get('version')
            source = port_data.get('source', 'auto')

            # Check if port already exists
            cursor.execute('''
                SELECT id, service, version FROM host_ports
                WHERE host_id = ? AND port = ? AND protocol = ?
            ''', (host_id, port_num, protocol))
            row = cursor.fetchone()

            if row:
                # Port exists - update
                port_id = row[0]
                existing_service = row[1]
                existing_version = row[2]

                new_service = service if service else existing_service
                new_version = version if version else existing_version

                cursor.execute('''
                    UPDATE host_ports
                    SET state = ?, service = ?, version = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (state, new_service, new_version, port_id))
            else:
                # Insert new port
                cursor.execute('''
                    INSERT INTO host_ports (host_id, port, protocol, state, service, version, source, evidence_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (host_id, port_num, protocol, state, service, version, source, evidence_id))

            count += 1
        except Exception as e:
            print(f"Error inserting port {port_data.get('port')}: {e}")

    return count


def extract_hosts_only(engagement_id, metadata, evidence_id, conn):
    """
    Extract hosts and ports from metadata WITHOUT linking evidence to hosts.
    Use this for tool_output evidence types where the scan file should stay in General.

    Args:
        engagement_id: The engagement ID
        metadata: Dict containing parsed tool output
        evidence_id: The evidence ID (for tracking port source)
        conn: Database connection

    Returns:
        Number of hosts created/updated
    """
    hosts = extract_hosts_from_metadata(metadata)
    host_count = 0

    for host_data in hosts:
        host_id = get_or_create_host(
            engagement_id,
            host_data['ip'],
            host_data.get('hostname'),
            host_data.get('os'),
            conn
        )
        if host_id:
            host_count += 1
            # Extract and insert ports for this host
            ports = extract_ports_from_metadata(metadata, host_data['ip'])
            if ports:
                insert_ports_for_host(host_id, ports, evidence_id, conn)

    return host_count


def extract_and_link_hosts_for_evidence(evidence_id, engagement_id, metadata, conn):
    """
    Extract hosts from metadata and link them to evidence.
    Also extracts and inserts port information.
    Use this for evidence that should be associated with specific hosts.

    Args:
        evidence_id: The evidence ID
        engagement_id: The engagement ID
        metadata: Dict containing parsed tool output
        conn: Database connection

    Returns:
        Number of hosts linked
    """
    hosts = extract_hosts_from_metadata(metadata)
    linked_count = 0

    for host_data in hosts:
        host_id = get_or_create_host(
            engagement_id,
            host_data['ip'],
            host_data.get('hostname'),
            host_data.get('os'),
            conn
        )
        if host_id:
            if link_evidence_to_host(evidence_id, host_id, source='auto', conn=conn):
                linked_count += 1

            # Extract and insert ports for this host
            ports = extract_ports_from_metadata(metadata, host_data['ip'])
            if ports:
                insert_ports_for_host(host_id, ports, evidence_id, conn)

    return linked_count


def get_hosts_for_engagement(engagement_id, conn):
    """
    Get all hosts for an engagement with evidence counts.

    Args:
        engagement_id: The engagement ID
        conn: Database connection

    Returns:
        List of host dicts with evidence_count
    """
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            h.id,
            h.ip,
            h.hostname,
            h.os,
            h.notes,
            h.rooted,
            h.shell,
            h.interested,
            h.not_interested,
            h.out_of_scope,
            h.flagged,
            h.reviewed,
            h.color_category,
            h.created_at,
            h.updated_at,
            COUNT(eh.evidence_id) as evidence_count,
            CASE
                WHEN (h.notes IS NOT NULL AND TRIM(h.notes) != '')
                  OR EXISTS (
                      SELECT 1 FROM host_notes hn
                      WHERE hn.host_id = h.id
                        AND hn.content IS NOT NULL
                        AND TRIM(hn.content) != ''
                  )
                THEN 1 ELSE 0
            END AS has_notes,
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM engagement_findings f
                    WHERE f.engagement_id = h.engagement_id
                      AND (
                          (f.ip_address IS NOT NULL AND f.ip_address = h.ip)
                          OR (f.hostname IS NOT NULL AND h.hostname IS NOT NULL
                              AND f.hostname = h.hostname)
                      )
                )
                THEN 1 ELSE 0
            END AS has_findings
        FROM hosts h
        LEFT JOIN evidence_hosts eh ON h.id = eh.host_id
        WHERE h.engagement_id = ?
        GROUP BY h.id
        ORDER BY h.ip
    ''', (engagement_id,))

    hosts = []
    for row in cursor.fetchall():
        hosts.append({
            'id': row[0],
            'ip': row[1],
            'hostname': row[2],
            'os': row[3],
            'notes': row[4],
            'rooted': bool(row[5]),
            'shell': bool(row[6]),
            'interested': bool(row[7]),
            'not_interested': bool(row[8]),
            'out_of_scope': bool(row[9]),
            'flagged': bool(row[10]),
            'reviewed': bool(row[11]),
            'color_category': row[12],
            'created_at': row[13],
            'updated_at': row[14],
            'evidence_count': row[15],
            'has_notes': bool(row[16]),
            'has_findings': bool(row[17]),
        })

    return hosts


def get_evidence_without_hosts(engagement_id, conn):
    """
    Get count of evidence items without any host assignment.

    Args:
        engagement_id: The engagement ID
        conn: Database connection

    Returns:
        Count of evidence without hosts
    """
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COUNT(*)
        FROM evidence e
        WHERE e.engagement_id = ?
        AND NOT EXISTS (
            SELECT 1 FROM evidence_hosts eh WHERE eh.evidence_id = e.id
        )
    ''', (engagement_id,))

    return cursor.fetchone()[0]

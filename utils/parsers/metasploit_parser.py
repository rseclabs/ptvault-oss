"""
Metasploit XML workspace export parser for PTVault.

This module parses Metasploit workspace XML exports and extracts
structured metadata including hosts, services, vulnerabilities, and credentials.
"""

import logging
from lxml import etree
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class MetasploitParser(BaseToolParser):
    """Parser for Metasploit XML workspace export files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is Metasploit XML workspace export.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file is Metasploit format, False otherwise
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()
            return root.tag == 'MetasploitV4' or root.tag == 'MetasploitV5'
        except Exception as e:
            logger.debug(f"Metasploit validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse Metasploit XML workspace export and extract structured metadata.

        Args:
            file_path: Path to the Metasploit XML file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with hosts, findings, credentials, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            metadata = {
                "tool": "metasploit",
                "workspace": root.findtext('.//workspace/name'),
                "summary": {
                    "total_hosts": 0,
                    "total_services": 0,
                    "total_vulns": 0,
                    "total_credentials": 0,
                    "total_loots": 0
                },
                "hosts": [],
                "findings": [],
                "credentials": []
            }

            # Parse hosts
            hosts = root.findall('.//host')
            metadata['summary']['total_hosts'] = len(hosts)

            for host_elem in hosts:
                # Extract host data
                ip = host_elem.findtext('address')
                if not ip:
                    continue

                host_data = {
                    'ip': ip,
                    'hostname': host_elem.findtext('name'),
                    'os': self._extract_os(host_elem),
                    'purpose': host_elem.findtext('purpose'),
                    'info': host_elem.findtext('info'),
                    'source': 'Metasploit'
                }

                # Remove None values
                host_data = self.filter_none(host_data)
                metadata['hosts'].append(host_data)

                # Parse services for this host
                services = host_elem.findall('.//service')
                metadata['summary']['total_services'] += len(services)

                # Parse vulnerabilities for this host
                vulns = host_elem.findall('.//vuln')
                for vuln in vulns:
                    metadata['summary']['total_vulns'] += 1

                    finding = {
                        'title': vuln.findtext('name'),
                        'severity': self._map_metasploit_severity(vuln.findtext('name')),
                        'description': vuln.findtext('info'),
                        'service': vuln.findtext('service'),
                        'port': vuln.findtext('port'),
                        'protocol': vuln.findtext('proto'),
                        'exploit_module': vuln.findtext('exploited_at'),
                        'references': self._extract_refs(vuln),
                        'tool': 'Metasploit'
                    }

                    # Remove None values
                    finding = self.filter_none(finding)
                    metadata['findings'].append(finding)

            # Parse credentials from creds section
            creds = root.findall('.//cred')
            metadata['summary']['total_credentials'] = len(creds)

            for cred_elem in creds:
                service_elem = cred_elem.find('.//service')

                credential = {
                    'username': cred_elem.findtext('user'),
                    'password': cred_elem.findtext('pass'),
                    'hash': cred_elem.findtext('hash'),
                    'service': service_elem.findtext('name') if service_elem is not None else None,
                    'port': service_elem.findtext('port') if service_elem is not None else None,
                    'protocol': service_elem.findtext('proto') if service_elem is not None else None,
                    'type': cred_elem.findtext('ptype'),
                    'tool': 'Metasploit'
                }

                # Remove None values
                credential = self.filter_none(credential)
                metadata['credentials'].append(credential)

            # Parse loot (collected files/data)
            loots = root.findall('.//loot')
            metadata['summary']['total_loots'] = len(loots)

            logger.info(
                f"Successfully parsed Metasploit XML: {metadata['summary']['total_hosts']} hosts, "
                f"{metadata['summary']['total_services']} services, "
                f"{metadata['summary']['total_vulns']} vulnerabilities, "
                f"{metadata['summary']['total_credentials']} credentials"
            )
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"Metasploit XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing Metasploit file {path}: {e}")
            return None

    def _extract_os(self, host_elem) -> Optional[str]:
        """
        Extract OS information from host element.

        Args:
            host_elem: XML host element

        Returns:
            str: OS string or None
        """
        os_name = host_elem.findtext('os_name')
        os_flavor = host_elem.findtext('os_flavor')
        os_sp = host_elem.findtext('os_sp')

        parts = [p for p in [os_name, os_flavor, os_sp] if p]
        return ' '.join(parts) if parts else None

    def _extract_refs(self, vuln_elem) -> Optional[str]:
        """
        Extract vulnerability references.

        Args:
            vuln_elem: XML vuln element

        Returns:
            str: Comma-separated references or None
        """
        refs = vuln_elem.findall('.//ref')
        if refs:
            ref_list = [ref.text for ref in refs if ref.text]
            return ', '.join(ref_list) if ref_list else None
        return None

    def _map_metasploit_severity(self, vuln_name: Optional[str]) -> str:
        """
        Map vulnerability name to severity (heuristic-based).

        Metasploit doesn't always include severity, so we use heuristics.

        Args:
            vuln_name: Vulnerability name

        Returns:
            str: Estimated severity level
        """
        if not vuln_name:
            return 'medium'

        name_lower = vuln_name.lower()

        # Critical indicators
        if any(word in name_lower for word in ['rce', 'remote code execution', 'unauthenticated']):
            return 'critical'

        # High indicators
        if any(word in name_lower for word in ['exploit', 'shell', 'command injection', 'sql injection']):
            return 'high'

        # Low indicators
        if any(word in name_lower for word in ['disclosure', 'information leak', 'banner']):
            return 'low'

        # Default to medium
        return 'medium'

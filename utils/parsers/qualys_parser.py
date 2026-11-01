"""
Qualys XML output parser for PTVault.

This module parses Qualys vulnerability scan XML reports and extracts
structured metadata including hosts, vulnerabilities, CVEs, and CVSS scores.
"""

import logging
from lxml import etree
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class QualysParser(BaseToolParser):
    """Parser for Qualys XML report files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is Qualys XML output.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file is Qualys format, False otherwise
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()
            # Qualys uses various root elements
            return root.tag in ['SCAN', 'ASSET_DATA_REPORT', 'KNOWLEDGE_BASE_VULN_LIST_OUTPUT']
        except Exception as e:
            logger.debug(f"Qualys validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse Qualys XML output and extract structured metadata.

        Args:
            file_path: Path to the Qualys XML file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with hosts, findings, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            metadata = {
                "tool": "qualys",
                "scan_date": root.findtext('.//DATETIME'),
                "scan_title": root.findtext('.//TITLE'),
                "summary": {
                    "total_hosts": 0,
                    "total_vulnerabilities": 0,
                    "by_severity": {
                        "Critical": 0,
                        "High": 0,
                        "Medium": 0,
                        "Low": 0,
                        "Info": 0
                    }
                },
                "hosts": [],
                "findings": []
            }

            # Parse hosts - handle both SCAN and ASSET_DATA_REPORT formats
            ip_elements = root.findall('.//IP')
            if not ip_elements:
                ip_elements = root.findall('.//HOST')

            metadata['summary']['total_hosts'] = len(ip_elements)

            for host_elem in ip_elements:
                # Extract IP address
                ip = host_elem.get('value') or host_elem.get('name') or host_elem.findtext('IP')

                if not ip:
                    continue

                # Extract host properties
                host_data = {
                    'ip': ip,
                    'hostname': (
                        host_elem.findtext('.//DNS') or
                        host_elem.findtext('.//HOSTNAME') or
                        host_elem.findtext('.//FQDN')
                    ),
                    'os': (
                        host_elem.findtext('.//OPERATING_SYSTEM') or
                        host_elem.findtext('.//OS')
                    ),
                    'source': 'Qualys'
                }

                # Remove None values
                host_data = self.filter_none(host_data)
                metadata['hosts'].append(host_data)

                # Parse vulnerabilities for this host
                vulns = host_elem.findall('.//VULN') or host_elem.findall('.//DETECTION')

                for vuln in vulns:
                    # Extract severity
                    severity_text = vuln.findtext('SEVERITY')
                    severity = self._map_qualys_severity(severity_text)

                    # Count by severity
                    metadata['summary']['by_severity'][severity.title()] += 1
                    metadata['summary']['total_vulnerabilities'] += 1

                    # Extract CVE list
                    cve_list = vuln.findtext('CVE_ID_LIST') or ''
                    cves = [cve.strip() for cve in cve_list.split(',') if cve.strip()]

                    finding = {
                        'title': vuln.findtext('TITLE'),
                        'qid': vuln.findtext('QID'),
                        'severity': severity,
                        'description': (
                            vuln.findtext('DIAGNOSIS') or
                            vuln.findtext('THREAT')
                        ),
                        'solution': (
                            vuln.findtext('SOLUTION') or
                            vuln.findtext('CONSEQUENCE')
                        ),
                        'cvss_score': (
                            vuln.findtext('CVSS_BASE') or
                            vuln.findtext('CVSS_SCORE')
                        ),
                        'cvss_vector': vuln.findtext('CVSS_VECTOR'),
                        'cve': cves[0] if cves else None,
                        'cves': cves if len(cves) > 1 else None,
                        'port': vuln.findtext('PORT'),
                        'protocol': vuln.findtext('PROTOCOL'),
                        'service': vuln.findtext('SERVICE'),
                        'exploitability': vuln.findtext('EXPLOITABILITY'),
                        'pci_flag': vuln.findtext('PCI_FLAG'),
                        'vendor_reference': vuln.findtext('VENDOR_REFERENCE_LIST'),
                        'bugtraq': vuln.findtext('BUGTRAQ_ID_LIST'),
                        'tool': 'Qualys'
                    }

                    # Remove None values
                    finding = self.filter_none(finding)
                    metadata['findings'].append(finding)

            logger.info(
                f"Successfully parsed Qualys XML: {metadata['summary']['total_hosts']} hosts, "
                f"{metadata['summary']['total_vulnerabilities']} vulnerabilities"
            )
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"Qualys XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing Qualys file {path}: {e}")
            return None

    def _map_qualys_severity(self, severity: Optional[str]) -> str:
        """
        Map Qualys severity levels to PTVault standard.

        Qualys uses: 5 (Critical/Urgent), 4 (Critical), 3 (Serious), 2 (Medium), 1 (Minimal)

        Args:
            severity: Qualys severity level

        Returns:
            str: Normalized severity level
        """
        if not severity:
            return 'info'

        severity_map = {
            '5': 'critical',
            '4': 'critical',
            '3': 'high',
            '2': 'medium',
            '1': 'low',
            '0': 'info'
        }

        return severity_map.get(severity, self.normalize_severity(severity))

"""
Rapid7 InsightVM (Nexpose) XML output parser for PTVault.

This module parses InsightVM/Nexpose XML reports and extracts
structured metadata including hosts, vulnerabilities, and services.
"""

import logging
from lxml import etree
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class InsightVMParser(BaseToolParser):
    """Parser for Rapid7 InsightVM/Nexpose XML report files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is InsightVM/Nexpose XML output.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file is InsightVM/Nexpose format, False otherwise
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()
            # InsightVM/Nexpose uses NexposeReport or XMLOutput
            return root.tag in ['NexposeReport', 'XMLOutput']
        except Exception as e:
            logger.debug(f"InsightVM validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse InsightVM/Nexpose XML output and extract structured metadata.

        Args:
            file_path: Path to the InsightVM XML file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with hosts, findings, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            metadata = {
                "tool": "insightvm",
                "scan_name": root.get('name'),
                "scan_date": root.get('generated'),
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

            # Parse nodes (hosts)
            nodes = root.findall('.//node')
            metadata['summary']['total_hosts'] = len(nodes)

            for node in nodes:
                # Extract IP address
                ip = node.get('address')
                if not ip:
                    continue

                # Extract hostname
                hostname = None
                names = node.findall('.//name')
                if names:
                    hostname = names[0].text

                # Extract OS
                os_info = None
                fingerprints = node.findall('.//fingerprint')
                if fingerprints:
                    os_elem = fingerprints[0].find('.//os')
                    if os_elem is not None:
                        os_info = os_elem.get('family') or os_elem.text

                host_data = {
                    'ip': ip,
                    'hostname': hostname,
                    'os': os_info,
                    'risk_score': node.get('risk-score'),
                    'source': 'InsightVM'
                }

                # Remove None values
                host_data = self.filter_none(host_data)
                metadata['hosts'].append(host_data)

                # Parse tests (vulnerabilities) for this node
                tests = node.findall('.//test')

                for test in tests:
                    # Get vulnerability details
                    vuln_id = test.get('id')
                    status = test.get('status')

                    # Only include vulnerable findings
                    if status != 'vulnerable-exploited' and status != 'vulnerable-version':
                        continue

                    metadata['summary']['total_vulnerabilities'] += 1

                    # Find vulnerability definition
                    vuln_def = root.find(f".//vulnerability[@id='{vuln_id}']")

                    if vuln_def is not None:
                        title = vuln_def.get('title')
                        severity_num = vuln_def.get('severity', '0')
                        severity = self._map_insightvm_severity(severity_num)

                        # Count by severity
                        metadata['summary']['by_severity'][severity.title()] += 1

                        # Extract CVEs
                        cves = []
                        refs = vuln_def.findall('.//reference[@source="CVE"]')
                        for ref in refs:
                            cve = ref.text
                            if cve:
                                cves.append(cve)

                        finding = {
                            'title': title,
                            'vuln_id': vuln_id,
                            'severity': severity,
                            'description': vuln_def.findtext('.//description'),
                            'solution': self._extract_solution(vuln_def),
                            'cvss_score': vuln_def.get('cvssScore'),
                            'cvss_vector': vuln_def.get('cvssVector'),
                            'cve': cves[0] if cves else None,
                            'cves': ', '.join(cves) if len(cves) > 1 else None,
                            'pci_severity': vuln_def.get('pciSeverity'),
                            'exploits': self._extract_exploits(vuln_def),
                            'port': test.get('port'),
                            'protocol': test.get('protocol'),
                            'service': test.get('service'),
                            'tool': 'InsightVM'
                        }

                        # Remove None values
                        finding = self.filter_none(finding)
                        metadata['findings'].append(finding)

            logger.info(
                f"Successfully parsed InsightVM XML: {metadata['summary']['total_hosts']} hosts, "
                f"{metadata['summary']['total_vulnerabilities']} vulnerabilities"
            )
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"InsightVM XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing InsightVM file {path}: {e}")
            return None

    def _map_insightvm_severity(self, severity: str) -> str:
        """
        Map InsightVM severity to PTVault standard.

        InsightVM uses: 0-10 scale or critical/severe/moderate

        Args:
            severity: InsightVM severity value

        Returns:
            str: Normalized severity level
        """
        # Try numeric severity (0-10 scale)
        try:
            severity_num = int(severity)
            if severity_num >= 9:
                return 'critical'
            elif severity_num >= 7:
                return 'high'
            elif severity_num >= 4:
                return 'medium'
            elif severity_num >= 1:
                return 'low'
            else:
                return 'info'
        except (ValueError, TypeError):
            pass

        # Try text severity
        return self.normalize_severity(severity)

    def _extract_solution(self, vuln_def) -> Optional[str]:
        """
        Extract solution/remediation text.

        Args:
            vuln_def: Vulnerability definition element

        Returns:
            str: Solution text or None
        """
        solution_elem = vuln_def.find('.//solution')
        if solution_elem is not None:
            # Get all text content
            return ''.join(solution_elem.itertext()).strip()
        return None

    def _extract_exploits(self, vuln_def) -> Optional[str]:
        """
        Extract exploit information.

        Args:
            vuln_def: Vulnerability definition element

        Returns:
            str: Comma-separated exploit IDs or None
        """
        exploit_refs = vuln_def.findall('.//reference[@source="EXPLOIT"]')
        if exploit_refs:
            exploits = [ref.text for ref in exploit_refs if ref.text]
            return ', '.join(exploits) if exploits else None
        return None

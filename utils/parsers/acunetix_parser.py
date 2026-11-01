"""
Acunetix XML output parser for PTVault.

This module parses Acunetix web vulnerability scanner XML reports and
extracts structured metadata including web vulnerabilities and affected URLs.
"""

import logging
from lxml import etree
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class AcunetixParser(BaseToolParser):
    """Parser for Acunetix XML report files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is Acunetix XML output.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file is Acunetix format, False otherwise
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()
            # Acunetix uses ScanGroup or WASReport as root
            return root.tag in ['ScanGroup', 'WASReport', 'Scan']
        except Exception as e:
            logger.debug(f"Acunetix validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse Acunetix XML output and extract structured metadata.

        Args:
            file_path: Path to the Acunetix XML file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with hosts, findings, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            metadata = {
                "tool": "acunetix",
                "scan_date": (
                    root.findtext('.//StartTime') or
                    root.findtext('.//ScanDate') or
                    root.findtext('.//Date')
                ),
                "summary": {
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

            hosts_set = set()

            # Find all ReportItem or Vulnerability elements
            vulns = (
                root.findall('.//ReportItem') or
                root.findall('.//Vulnerability') or
                root.findall('.//Item')
            )

            metadata['summary']['total_vulnerabilities'] = len(vulns)

            for vuln in vulns:
                # Extract target URL
                url = (
                    vuln.findtext('Affects') or
                    vuln.findtext('URL') or
                    vuln.findtext('TargetURL')
                )

                if url:
                    host = self.extract_host_from_url(url)
                    if host:
                        hosts_set.add(host)

                # Extract severity
                severity_raw = (
                    vuln.findtext('Severity') or
                    vuln.findtext('severity') or
                    vuln.findtext('Type')
                )
                severity = self._map_acunetix_severity(severity_raw)

                # Count by severity
                metadata['summary']['by_severity'][severity.title()] += 1

                # Extract CVSS if available
                cvss_score = (
                    vuln.findtext('CVSS') or
                    vuln.findtext('cvss_score') or
                    vuln.findtext('CVSSScore')
                )

                # Extract CWE
                cwe = (
                    vuln.findtext('CWE') or
                    vuln.findtext('cwe_id')
                )

                finding = {
                    'title': (
                        vuln.findtext('Name') or
                        vuln.findtext('name') or
                        vuln.findtext('Title')
                    ),
                    'severity': severity,
                    'description': (
                        vuln.findtext('Description') or
                        vuln.findtext('Details')
                    ),
                    'solution': (
                        vuln.findtext('Recommendation') or
                        vuln.findtext('Solution') or
                        vuln.findtext('Remediation')
                    ),
                    'url': url,
                    'parameter': (
                        vuln.findtext('Parameter') or
                        vuln.findtext('AffectedParameter')
                    ),
                    'method': vuln.findtext('Method'),
                    'request': vuln.findtext('Request'),
                    'response': vuln.findtext('Response'),
                    'cvss_score': cvss_score,
                    'cwe': cwe,
                    'owasp': vuln.findtext('OWASP'),
                    'impact': vuln.findtext('Impact'),
                    'references': self._extract_references(vuln),
                    'tool': 'Acunetix'
                }

                # Remove None values
                finding = self.filter_none(finding)
                metadata['findings'].append(finding)

            # Convert hosts set to list
            metadata['hosts'] = [
                {'ip': host, 'source': 'Acunetix'} for host in sorted(hosts_set)
            ]

            logger.info(
                f"Successfully parsed Acunetix XML: {len(hosts_set)} hosts, "
                f"{metadata['summary']['total_vulnerabilities']} vulnerabilities"
            )
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"Acunetix XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing Acunetix file {path}: {e}")
            return None

    def _map_acunetix_severity(self, severity: Optional[str]) -> str:
        """
        Map Acunetix severity to PTVault standard.

        Acunetix uses: critical, high, medium, low, informational

        Args:
            severity: Acunetix severity string

        Returns:
            str: Normalized severity level
        """
        if not severity:
            return 'medium'

        severity_lower = severity.lower()

        severity_map = {
            '4': 'critical',
            '3': 'high',
            '2': 'medium',
            '1': 'low',
            '0': 'info'
        }

        # Try numeric mapping first
        if severity in severity_map:
            return severity_map[severity]

        # Use base normalize method
        return self.normalize_severity(severity)

    def _extract_references(self, vuln_elem) -> Optional[str]:
        """
        Extract vulnerability references.

        Args:
            vuln_elem: XML vulnerability element

        Returns:
            str: Comma-separated references or None
        """
        refs = (
            vuln_elem.findall('.//Reference') or
            vuln_elem.findall('.//reference')
        )

        if refs:
            ref_list = []
            for ref in refs:
                ref_text = ref.text or ref.findtext('URL')
                if ref_text:
                    ref_list.append(ref_text)

            return ', '.join(ref_list) if ref_list else None

        # Try single Reference field
        ref_text = vuln_elem.findtext('References') or vuln_elem.findtext('Reference')
        return ref_text if ref_text else None

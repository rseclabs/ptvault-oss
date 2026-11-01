"""
OWASP ZAP XML output parser for PTVault.

This module parses OWASP ZAP XML report files and extracts structured
metadata including web vulnerabilities, alerts, and affected URLs.
"""

import logging
from lxml import etree
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class ZAPParser(BaseToolParser):
    """Parser for OWASP ZAP XML report files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is OWASP ZAP XML output.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file has OWASPZAPReport root element, False otherwise
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()
            return root.tag == 'OWASPZAPReport'
        except Exception as e:
            logger.debug(f"ZAP validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse OWASP ZAP XML output and extract structured metadata.

        Args:
            file_path: Path to the ZAP XML file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with hosts, findings, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            metadata = {
                "tool": "zap",
                "tool_version": root.get('version'),
                "generated": root.get('generated'),
                "summary": {
                    "total_alerts": 0,
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

            # Parse sites and alerts
            for site in root.findall('.//site'):
                site_url = site.get('name')
                if site_url:
                    host = self.extract_host_from_url(site_url)
                    if host:
                        hosts_set.add(host)

                # Parse alerts for this site
                for alert in site.findall('.//alertitem'):
                    # Extract alert data
                    risk_code = alert.findtext('riskcode', '0')
                    risk_desc = alert.findtext('riskdesc', 'Informational')
                    severity = self._map_zap_risk(risk_code, risk_desc)

                    # Count by severity
                    metadata['summary']['by_severity'][severity.title()] += 1
                    metadata['summary']['total_alerts'] += 1

                    finding = {
                        'title': alert.findtext('name'),
                        'severity': severity,
                        'description': alert.findtext('desc'),
                        'solution': alert.findtext('solution'),
                        'url': alert.findtext('uri'),
                        'method': alert.findtext('method'),
                        'param': alert.findtext('param'),
                        'attack': alert.findtext('attack'),
                        'evidence': alert.findtext('evidence'),
                        'cwe': alert.findtext('cweid'),
                        'wasc': alert.findtext('wascid'),
                        'reference': alert.findtext('reference'),
                        'confidence': alert.findtext('confidence'),
                        'tool': 'ZAP'
                    }

                    # Remove None values
                    finding = self.filter_none(finding)
                    metadata['findings'].append(finding)

            # Convert hosts set to list of dicts
            metadata['hosts'] = [
                {'ip': host, 'source': 'ZAP'} for host in sorted(hosts_set)
            ]

            logger.info(
                f"Successfully parsed ZAP XML: {len(hosts_set)} hosts, "
                f"{metadata['summary']['total_alerts']} alerts"
            )
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"ZAP XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing ZAP file {path}: {e}")
            return None

    def _map_zap_risk(self, risk_code: str, risk_desc: str) -> str:
        """
        Map ZAP risk codes to PTVault severity.

        Args:
            risk_code: ZAP risk code (0-3)
            risk_desc: ZAP risk description

        Returns:
            str: Normalized severity level
        """
        # Try risk code first
        risk_map = {
            '3': 'high',
            '2': 'medium',
            '1': 'low',
            '0': 'info'
        }

        if risk_code in risk_map:
            return risk_map[risk_code]

        # Fall back to risk description
        if risk_desc:
            desc_lower = risk_desc.lower()
            if 'high' in desc_lower:
                return 'high'
            elif 'medium' in desc_lower:
                return 'medium'
            elif 'low' in desc_lower:
                return 'low'

        return 'info'

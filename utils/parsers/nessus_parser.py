"""
Nessus XML output parser for PTVault.

This module parses Nessus .nessus XML export files and extracts structured
metadata including hosts, vulnerabilities, CVEs, CVSS scores, and severity information.
"""

import logging
from lxml import etree

from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class NessusToolParser(BaseToolParser):
    """Parser for Nessus XML output files (.nessus format)."""

    def validate(self, file_path=None):
        """
        Validate that the file is Nessus XML output by checking for <NessusClientData_v2> root element.

        Args:
            file_path: Path to the file to validate (falls back to self.file_path)

        Returns:
            bool: True if file has <NessusClientData_v2> root element, False otherwise
        """
        path = file_path if file_path is not None else self.file_path
        try:
            # Parse with entity resolution disabled for security (XXE protection)
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()
            return root.tag == 'NessusClientData_v2'
        except Exception as e:
            logger.debug(f"Validation failed for {path}: {e}")
            return False

    def parse(self, file_path=None):
        """
        Parse Nessus XML output and extract structured metadata.

        Args:
            file_path: Path to the Nessus XML file

        Returns:
            dict: Structured metadata with hosts, vulnerabilities, CVEs, or None if parsing fails
        """
        path = file_path if file_path is not None else self.file_path
        try:
            # Parse with entity resolution disabled for security (XXE protection)
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            # Extract scan metadata
            policy = root.find('.//Policy')
            policy_name = policy.findtext('policyName') if policy is not None else None

            report = root.find('.//Report')
            report_name = report.get('name') if report is not None else None

            metadata = {
                "tool": "nessus",
                "policy_name": policy_name,
                "scan_name": report_name,
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
                "hosts": []
            }

            if report is None:
                logger.warning(f"No Report element found in {path}")
                return metadata

            # Extract report hosts
            report_hosts = report.findall('ReportHost')
            metadata['summary']['total_hosts'] = len(report_hosts)

            for report_host in report_hosts:
                host_name = report_host.get('name')

                # Get host properties
                host_properties = {}
                for tag in report_host.findall('.//HostProperties/tag'):
                    tag_name = tag.get('name')
                    tag_value = tag.text
                    if tag_name and tag_value:
                        host_properties[tag_name] = tag_value

                # Extract host data
                host_data = {
                    "ip": host_name,
                    "hostname": host_properties.get('host-fqdn'),
                    "os": host_properties.get('operating-system'),
                    "mac": host_properties.get('mac-address'),
                    "vulnerabilities": []
                }

                # Extract vulnerabilities (filter by severity >= 1 for Medium/High/Critical only)
                report_items = report_host.findall('ReportItem')
                for item in report_items:
                    severity = int(item.get('severity', 0))

                    # Count all severities for summary
                    severity_map = {0: 'Info', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical'}
                    severity_name = severity_map.get(severity, 'Info')
                    metadata['summary']['by_severity'][severity_name] += 1
                    metadata['summary']['total_vulnerabilities'] += 1

                    # Only include detailed info for Medium/High/Critical (severity >= 1)
                    if severity >= 1:
                        # Extract CVEs
                        cves = [cve.text for cve in item.findall('cve') if cve.text]

                        vuln_data = {
                            "plugin_id": item.get('pluginID'),
                            "plugin_name": item.get('pluginName'),
                            "plugin_family": item.get('pluginFamily'),
                            "port": item.get('port'),
                            "service": item.get('svc_name'),
                            "protocol": item.get('protocol'),
                            "severity": severity,
                            "risk_factor": item.findtext('risk_factor'),
                            "synopsis": item.findtext('synopsis'),
                            "description": item.findtext('description'),
                            "solution": item.findtext('solution'),
                            "plugin_output": item.findtext('plugin_output'),
                            "cves": cves,
                            "cvss_base_score": item.findtext('cvss_base_score'),
                            "cvss_vector": item.findtext('cvss_vector'),
                            "exploit_available": item.findtext('exploit_available')
                        }

                        host_data['vulnerabilities'].append(vuln_data)

                metadata['hosts'].append(host_data)

            logger.info(
                f"Successfully parsed Nessus XML: {metadata['summary']['total_hosts']} hosts, "
                f"{metadata['summary']['total_vulnerabilities']} vulnerabilities "
                f"(Critical: {metadata['summary']['by_severity']['Critical']}, "
                f"High: {metadata['summary']['by_severity']['High']}, "
                f"Medium: {metadata['summary']['by_severity']['Medium']})"
            )
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"Nessus XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing {path}: {e}")
            return None

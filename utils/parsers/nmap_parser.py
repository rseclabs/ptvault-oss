"""
Nmap XML output parser for PTVault.

This module parses nmap XML output files (-oX flag) and extracts structured
metadata including hosts, ports, services, and OS detection information.
"""

import logging
from datetime import datetime
from libnmap.parser import NmapParser, NmapParserException
import xml.etree.ElementTree as ET

from .base_parser import BaseToolParser


logger = logging.getLogger(__name__)


class NmapToolParser(BaseToolParser):
    """Parser for nmap XML output files."""

    def validate(self, file_path=None):
        """
        Validate that the file is nmap XML output by checking for <nmaprun> root element.

        Args:
            file_path: Path to the file to validate (falls back to self.file_path)

        Returns:
            bool: True if file has <nmaprun> root element, False otherwise
        """
        path = file_path if file_path is not None else self.file_path
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            return root.tag == 'nmaprun'
        except Exception as e:
            logger.debug(f"Validation failed for {path}: {e}")
            return False

    def parse(self, file_path=None):
        """
        Parse nmap XML output and extract structured metadata.

        Args:
            file_path: Path to the nmap XML file

        Returns:
            dict: Structured metadata with hosts, ports, services, OS info, or None if parsing fails
        """
        path = file_path if file_path is not None else self.file_path
        try:
            # Parse using libnmap for clean API access
            nmap_report = NmapParser.parse_fromfile(path)

            # Extract scan metadata
            metadata = {
                "tool": "nmap",
                "tool_version": nmap_report.version,
                "scan_type": nmap_report.scan_type,
                "scan_args": nmap_report.commandline,
                "start_time": self._format_timestamp(nmap_report.started),
                "end_time": self._format_timestamp(nmap_report.endtime),
                "summary": {
                    "hosts_total": nmap_report.hosts_total,
                    "hosts_up": nmap_report.hosts_up,
                    "hosts_down": nmap_report.hosts_down
                },
                "hosts": []
            }

            # Extract host information (only up hosts)
            for host in nmap_report.hosts:
                if host.status == 'up':
                    host_data = {
                        "ip": host.address,
                        "hostname": host.hostnames[0] if host.hostnames else None,
                        "status": host.status,
                        "os": self._extract_os_info(host),
                        "open_ports": []
                    }

                    # Extract open ports with service information
                    for service in host.services:
                        if service.state == 'open':
                            port_data = {
                                "port": service.port,
                                "protocol": service.protocol,
                                "state": service.state,
                                "service": service.service,
                                "product": service.service_dict.get('product'),
                                "version": service.service_dict.get('version'),
                                "extrainfo": service.service_dict.get('extrainfo')
                            }
                            host_data["open_ports"].append(port_data)

                    metadata["hosts"].append(host_data)

            logger.info(f"Successfully parsed nmap XML: {len(metadata['hosts'])} hosts, {metadata['summary']['hosts_total']} total")
            return metadata

        except NmapParserException as e:
            logger.error(f"Nmap parser error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing {path}: {e}")
            return None

    def _format_timestamp(self, timestamp):
        """
        Convert Unix timestamp to ISO 8601 format.

        Args:
            timestamp: Unix timestamp (int or str)

        Returns:
            str: ISO 8601 formatted timestamp, or None if invalid
        """
        if timestamp is None:
            return None
        try:
            timestamp_int = int(timestamp)
            dt = datetime.fromtimestamp(timestamp_int)
            return dt.isoformat()
        except (ValueError, TypeError):
            return None

    def _extract_os_info(self, host):
        """
        Extract OS detection information from host.

        Args:
            host: NmapHost object

        Returns:
            str: OS description with accuracy, or None if no OS detected
        """
        if hasattr(host, 'os_fingerprinted') and host.os_fingerprinted:
            # Get the first (most accurate) OS match
            if hasattr(host, 'os_match_probabilities') and host.os_match_probabilities():
                best_match = host.os_match_probabilities()[0]
                if hasattr(best_match, 'name') and hasattr(best_match, 'accuracy'):
                    return f"{best_match.name} ({best_match.accuracy}% accuracy)"
        return None

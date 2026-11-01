"""
Burp Suite XML output parser for PTVault.

This module parses Burp Suite XML export files and extracts structured
metadata including vulnerabilities, severity, confidence, and remediation details.
"""

import logging
from lxml import etree

from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class BurpToolParser(BaseToolParser):
    """Parser for Burp Suite XML output files."""

    def validate(self, file_path=None):
        """
        Validate that the file is Burp Suite XML output by checking for <issues> root element.

        Args:
            file_path: Path to the file to validate (falls back to self.file_path)

        Returns:
            bool: True if file has <issues> root element, False otherwise
        """
        path = file_path if file_path is not None else self.file_path
        try:
            # Parse with entity resolution disabled for security (XXE protection)
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()
            return root.tag == 'issues'
        except Exception as e:
            logger.debug(f"Validation failed for {path}: {e}")
            return False

    def parse(self, file_path=None):
        """
        Parse Burp Suite XML output and extract structured metadata.

        Args:
            file_path: Path to the Burp Suite XML file

        Returns:
            dict: Structured metadata with issues, severity, confidence, or None if parsing fails
        """
        path = file_path if file_path is not None else self.file_path
        try:
            # Parse with entity resolution disabled for security (XXE protection)
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(path, parser)
            root = tree.getroot()

            # Extract scan metadata
            metadata = {
                "tool": "burp_suite",
                "tool_version": root.get('burpVersion'),
                "export_time": root.get('exportTime'),
                "summary": {
                    "total_issues": 0,
                    "by_severity": {
                        "High": 0,
                        "Medium": 0,
                        "Low": 0,
                        "Information": 0
                    },
                    "by_confidence": {
                        "Certain": 0,
                        "Firm": 0,
                        "Tentative": 0
                    }
                },
                "issues": []
            }

            # Extract issues
            issues = root.findall('issue')
            metadata['summary']['total_issues'] = len(issues)

            for issue in issues:
                # Extract severity and confidence for counting
                severity = issue.findtext('severity')
                confidence = issue.findtext('confidence')

                # Count by severity
                if severity in metadata['summary']['by_severity']:
                    metadata['summary']['by_severity'][severity] += 1

                # Count by confidence
                if confidence in metadata['summary']['by_confidence']:
                    metadata['summary']['by_confidence'][confidence] += 1

                # Extract issue details
                issue_data = {
                    "serial_number": issue.findtext('serialNumber'),
                    "type": issue.findtext('type'),
                    "name": issue.findtext('name'),
                    "host": issue.findtext('host'),
                    "path": issue.findtext('path'),
                    "location": issue.findtext('location'),
                    "severity": severity,
                    "confidence": confidence,
                    "issue_detail": issue.findtext('issueDetail'),
                    "remediation": issue.findtext('remediationDetail') or issue.findtext('remediationBackground')
                }

                metadata['issues'].append(issue_data)

            logger.info(f"Successfully parsed Burp Suite XML: {metadata['summary']['total_issues']} issues")
            return metadata

        except etree.XMLSyntaxError as e:
            logger.error(f"Burp Suite XML syntax error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing {path}: {e}")
            return None

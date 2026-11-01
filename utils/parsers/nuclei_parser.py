"""
Nuclei JSON output parser for PTVault.

This module parses Nuclei JSON/JSONL output files and extracts structured
metadata including template-based findings, severity, and affected hosts.
"""

import json
import logging
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class NucleiParser(BaseToolParser):
    """Parser for Nuclei JSON/JSONL output files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is Nuclei JSON/JSONL output.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file is valid Nuclei format, False otherwise
        """
        path = file_path or self.file_path
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return False

                # Try parsing entire file as JSON first
                try:
                    data = json.loads(content)

                    # Check if it's a list of nuclei results
                    if isinstance(data, list):
                        if not data:
                            return False
                        # Check first item
                        return (
                            isinstance(data[0], dict) and
                            ('template-id' in data[0] or 'templateID' in data[0] or
                             'template' in data[0] or 'info' in data[0])
                        )
                    # Check if it's a single result
                    elif isinstance(data, dict):
                        return (
                            'template-id' in data or 'templateID' in data or
                            'template' in data or 'info' in data
                        )
                except json.JSONDecodeError:
                    # Try as JSONL (one JSON per line)
                    first_line = content.split('\n')[0].strip()
                    if first_line:
                        data = json.loads(first_line)
                        return (
                            isinstance(data, dict) and
                            ('template-id' in data or 'templateID' in data or
                             'template' in data or 'info' in data)
                        )

                return False
        except (json.JSONDecodeError, FileNotFoundError, UnicodeDecodeError) as e:
            logger.debug(f"Nuclei validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse Nuclei JSON/JSONL output and extract structured metadata.

        Args:
            file_path: Path to the Nuclei file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with hosts, findings, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            results = []

            with open(path, 'r', encoding='utf-8') as f:
                # Handle both single JSON and JSONL (one JSON per line)
                content = f.read().strip()

                # Try as single JSON first
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        results = data
                    else:
                        results = [data]
                except json.JSONDecodeError:
                    # Try as JSONL
                    for line in content.split('\n'):
                        line = line.strip()
                        if line:
                            try:
                                results.append(json.loads(line))
                            except json.JSONDecodeError as e:
                                logger.warning(f"Skipping invalid JSON line: {e}")

            if not results:
                logger.error(f"No valid JSON data found in {path}")
                return None

            metadata = {
                "tool": "nuclei",
                "summary": {
                    "total_findings": len(results),
                    "by_severity": {
                        "Critical": 0,
                        "High": 0,
                        "Medium": 0,
                        "Low": 0,
                        "Info": 0
                    },
                    "unique_templates": 0,
                    "unique_hosts": 0
                },
                "hosts": [],
                "findings": []
            }

            hosts_set = set()
            templates_set = set()

            for result in results:
                # Extract host
                host = (
                    result.get('host') or
                    result.get('matched-at') or
                    result.get('matched_at') or
                    result.get('url')
                )

                if host:
                    extracted_host = self.extract_host_from_url(host)
                    if extracted_host:
                        hosts_set.add(extracted_host)

                # Extract info block
                info = result.get('info', {})

                # Extract template ID
                template_id = (
                    result.get('template-id') or
                    result.get('templateID') or
                    result.get('template') or
                    info.get('name', 'unknown')
                )
                templates_set.add(template_id)

                # Extract severity
                severity_raw = (
                    info.get('severity') or
                    result.get('severity') or
                    'info'
                )
                severity = self.normalize_severity(severity_raw)

                # Count by severity
                metadata['summary']['by_severity'][severity.title()] += 1

                # Extract tags
                tags = info.get('tags', [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',')]

                # Build finding
                finding = {
                    'title': (
                        info.get('name') or
                        result.get('name') or
                        template_id
                    ),
                    'template_id': template_id,
                    'severity': severity,
                    'description': (
                        info.get('description') or
                        result.get('description')
                    ),
                    'url': (
                        result.get('matched-at') or
                        result.get('matched_at') or
                        result.get('url') or
                        host
                    ),
                    'matcher_name': result.get('matcher-name') or result.get('matcher_name'),
                    'extractor_name': result.get('extractor-name') or result.get('extractor_name'),
                    'extracted_results': result.get('extracted-results') or result.get('extracted_results'),
                    'curl_command': result.get('curl-command') or result.get('curl_command'),
                    'tags': ', '.join(tags) if tags else None,
                    'reference': ', '.join(info.get('reference', [])) if info.get('reference') else None,
                    'cve': ', '.join(info.get('classification', {}).get('cve-id', [])),
                    'cwe': ', '.join(info.get('classification', {}).get('cwe-id', [])),
                    'tool': 'Nuclei'
                }

                # Remove None values
                finding = self.filter_none(finding)
                metadata['findings'].append(finding)

            # Update summary
            metadata['summary']['unique_templates'] = len(templates_set)
            metadata['summary']['unique_hosts'] = len(hosts_set)

            # Convert hosts set to list
            metadata['hosts'] = [
                {'ip': host, 'source': 'Nuclei'} for host in sorted(hosts_set)
            ]

            logger.info(
                f"Successfully parsed Nuclei output: {len(hosts_set)} hosts, "
                f"{len(results)} findings from {len(templates_set)} templates"
            )
            return metadata

        except FileNotFoundError:
            logger.error(f"Nuclei file not found: {path}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing Nuclei file {path}: {e}")
            return None

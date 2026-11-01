"""
BloodHound JSON output parser for PTVault.

This module parses BloodHound JSON data exports and extracts
structured metadata including Active Directory objects, relationships, and attack paths.
"""

import json
import logging
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class BloodHoundParser(BaseToolParser):
    """Parser for BloodHound JSON export files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is BloodHound JSON output.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file is BloodHound format, False otherwise
        """
        path = file_path or self.file_path
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # BloodHound JSON typically has these top-level keys
                return (
                    isinstance(data, dict) and
                    ('data' in data or 'nodes' in data or 'edges' in data or
                     'meta' in data or 'computers' in data or 'users' in data or
                     'groups' in data or 'domains' in data)
                )
        except (json.JSONDecodeError, FileNotFoundError, UnicodeDecodeError) as e:
            logger.debug(f"BloodHound validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse BloodHound JSON output and extract structured metadata.

        Args:
            file_path: Path to the BloodHound JSON file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with AD objects, relationships, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = {
                "tool": "bloodhound",
                "summary": {
                    "total_computers": 0,
                    "total_users": 0,
                    "total_groups": 0,
                    "total_domains": 0,
                    "total_relationships": 0,
                    "high_value_targets": 0
                },
                "hosts": [],
                "findings": [],
                "credentials": []
            }

            # Parse different BloodHound data formats
            computers = []
            users = []
            groups = []
            domains = []

            # Extract from nested data structure
            if 'data' in data:
                inner_data = data['data']
                computers = inner_data.get('computers', [])
                users = inner_data.get('users', [])
                groups = inner_data.get('groups', [])
                domains = inner_data.get('domains', [])
            else:
                # Direct format
                computers = data.get('computers', [])
                users = data.get('users', [])
                groups = data.get('groups', [])
                domains = data.get('domains', [])

            # Update summary counts
            metadata['summary']['total_computers'] = len(computers)
            metadata['summary']['total_users'] = len(users)
            metadata['summary']['total_groups'] = len(groups)
            metadata['summary']['total_domains'] = len(domains)

            # Parse computers (hosts)
            for computer in computers:
                properties = computer.get('Properties', {})

                hostname = (
                    properties.get('name') or
                    properties.get('hostname') or
                    computer.get('ObjectIdentifier')
                )

                if not hostname:
                    continue

                # Track high value targets
                if properties.get('highvalue', False):
                    metadata['summary']['high_value_targets'] += 1

                host_data = {
                    'ip': properties.get('ipaddress'),
                    'hostname': hostname,
                    'os': properties.get('operatingsystem'),
                    'enabled': properties.get('enabled'),
                    'domain': properties.get('domain'),
                    'high_value': properties.get('highvalue'),
                    'source': 'BloodHound'
                }

                # Remove None values
                host_data = self.filter_none(host_data)
                metadata['hosts'].append(host_data)

            # Parse users - look for privileged accounts or findings
            for user in users:
                properties = user.get('Properties', {})

                username = properties.get('name') or properties.get('samaccountname')

                if not username:
                    continue

                # Check for privileged or interesting users
                if properties.get('admincount', False) or properties.get('highvalue', False):
                    metadata['summary']['high_value_targets'] += 1

                    finding = {
                        'title': f"Privileged User Account: {username}",
                        'severity': 'high',
                        'description': self._build_user_description(properties),
                        'username': username,
                        'domain': properties.get('domain'),
                        'enabled': properties.get('enabled'),
                        'tool': 'BloodHound'
                    }

                    finding = self.filter_none(finding)
                    metadata['findings'].append(finding)

                # Check for password not required or never expires
                if properties.get('passwordnotreqd', False):
                    finding = {
                        'title': f"Password Not Required: {username}",
                        'severity': 'medium',
                        'description': f"User {username} does not require a password",
                        'username': username,
                        'domain': properties.get('domain'),
                        'tool': 'BloodHound'
                    }
                    finding = self.filter_none(finding)
                    metadata['findings'].append(finding)

            # Parse groups - look for privileged groups
            privileged_groups = [
                'Domain Admins', 'Enterprise Admins', 'Administrators',
                'Backup Operators', 'Account Operators', 'Server Operators'
            ]

            for group in groups:
                properties = group.get('Properties', {})
                group_name = properties.get('name')

                if not group_name:
                    continue

                # Check if privileged group
                if any(priv in group_name for priv in privileged_groups):
                    members = group.get('Members', [])

                    if members:
                        finding = {
                            'title': f"Privileged Group Membership: {group_name}",
                            'severity': 'high',
                            'description': f"Group {group_name} has {len(members)} members",
                            'member_count': len(members),
                            'tool': 'BloodHound'
                        }
                        finding = self.filter_none(finding)
                        metadata['findings'].append(finding)

            # Count relationships/edges
            if 'edges' in data:
                metadata['summary']['total_relationships'] = len(data['edges'])
            elif 'data' in data and 'edges' in data['data']:
                metadata['summary']['total_relationships'] = len(data['data']['edges'])

            logger.info(
                f"Successfully parsed BloodHound JSON: "
                f"{metadata['summary']['total_computers']} computers, "
                f"{metadata['summary']['total_users']} users, "
                f"{metadata['summary']['total_groups']} groups, "
                f"{metadata['summary']['high_value_targets']} high-value targets"
            )
            return metadata

        except FileNotFoundError:
            logger.error(f"BloodHound file not found: {path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"BloodHound JSON parse error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing BloodHound file {path}: {e}")
            return None

    def _build_user_description(self, properties: Dict) -> str:
        """
        Build a description for a privileged user.

        Args:
            properties: User properties dictionary

        Returns:
            str: Description text
        """
        parts = []

        if properties.get('admincount'):
            parts.append("Admin Count set")

        if properties.get('highvalue'):
            parts.append("High Value target")

        if not properties.get('enabled', True):
            parts.append("Account disabled")

        if properties.get('pwdneverexpires'):
            parts.append("Password never expires")

        if properties.get('dontreqpreauth'):
            parts.append("Does not require pre-authentication")

        description = f"Privileged user account with: {', '.join(parts)}" if parts else "Privileged user account"

        return description

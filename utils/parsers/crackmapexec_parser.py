"""
CrackMapExec log output parser for PTVault.

This module parses CrackMapExec log files and extracts
structured metadata including hosts, credentials, and lateral movement findings.
"""

import re
import logging
from typing import Dict, List, Optional
from .base_parser import BaseToolParser

logger = logging.getLogger(__name__)


class CrackMapExecParser(BaseToolParser):
    """Parser for CrackMapExec log files."""

    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is CrackMapExec log output.

        Args:
            file_path: Path to the file to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file appears to be CME output, False otherwise
        """
        path = file_path or self.file_path
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read first few lines
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    # Look for CME-specific patterns
                    if any(marker in line for marker in ['[CME]', '[SMB]', '[WINRM]', '[MSSQL]', '[SSH]', 'crackmapexec']):
                        return True
            return False
        except (FileNotFoundError, UnicodeDecodeError) as e:
            logger.debug(f"CrackMapExec validation failed for {path}: {e}")
            return False

    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse CrackMapExec log output and extract structured metadata.

        Args:
            file_path: Path to the CME log file (uses self.file_path if not provided)

        Returns:
            dict: Structured metadata with hosts, credentials, findings, or None if parsing fails
        """
        path = file_path or self.file_path
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            metadata = {
                "tool": "crackmapexec",
                "summary": {
                    "total_hosts": 0,
                    "total_credentials": 0,
                    "pwned_hosts": 0,
                    "findings": 0
                },
                "hosts": [],
                "findings": [],
                "credentials": []
            }

            hosts_set = set()
            credentials_set = set()
            pwned_hosts = set()

            # Patterns for parsing CME output
            patterns = {
                'host': re.compile(r'\[([^\]]+)\]\s+(\d+\.\d+\.\d+\.\d+)'),
                'success_auth': re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+.*\s+(\S+):(\S+)\s+\(.*\)\s*(\(Pwn3d!\))?'),
                'pwned': re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+.*Pwn3d!'),
                'share': re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+.*\[(ADMIN\$|C\$|IPC\$|SYSVOL|NETLOGON|[^\]]+)\]'),
                'sam_dump': re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+.*Dumping SAM hashes'),
                'lsa_dump': re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+.*Dumping LSA secrets'),
                'ntds': re.compile(r'(\d+\.\d+\.\d+\.\d+)\s+.*Dumping the NTDS'),
            }

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Extract hosts
                host_match = patterns['host'].search(line)
                if host_match:
                    protocol = host_match.group(1)
                    ip = host_match.group(2)
                    hosts_set.add(ip)

                # Check for successful authentication
                auth_match = patterns['success_auth'].search(line)
                if auth_match:
                    ip = auth_match.group(1)
                    username = auth_match.group(2)
                    password = auth_match.group(3)
                    is_pwned = auth_match.group(4) is not None

                    # Track credential
                    cred_tuple = (username, password)
                    if cred_tuple not in credentials_set:
                        credentials_set.add(cred_tuple)

                        credential = {
                            'username': username,
                            'password': password if password != 'xxxxxxxx' else None,
                            'host': ip,
                            'tool': 'CrackMapExec'
                        }
                        credential = self.filter_none(credential)
                        metadata['credentials'].append(credential)

                    # Track pwned host
                    if is_pwned:
                        pwned_hosts.add(ip)

                # Check for pwned indicator
                if patterns['pwned'].search(line):
                    pwned_match = patterns['pwned'].search(line)
                    if pwned_match:
                        pwned_hosts.add(pwned_match.group(1))

                # Check for sensitive operations
                if patterns['sam_dump'].search(line):
                    match = patterns['sam_dump'].search(line)
                    finding = {
                        'title': f"SAM Database Dumped on {match.group(1)}",
                        'severity': 'high',
                        'description': f"Successfully dumped SAM hashes from {match.group(1)}",
                        'tool': 'CrackMapExec'
                    }
                    metadata['findings'].append(finding)

                if patterns['lsa_dump'].search(line):
                    match = patterns['lsa_dump'].search(line)
                    finding = {
                        'title': f"LSA Secrets Dumped on {match.group(1)}",
                        'severity': 'high',
                        'description': f"Successfully dumped LSA secrets from {match.group(1)}",
                        'tool': 'CrackMapExec'
                    }
                    metadata['findings'].append(finding)

                if patterns['ntds'].search(line):
                    match = patterns['ntds'].search(line)
                    finding = {
                        'title': f"NTDS.dit Dumped on {match.group(1)}",
                        'severity': 'critical',
                        'description': f"Successfully dumped NTDS.dit from {match.group(1)} (Domain Controller)",
                        'tool': 'CrackMapExec'
                    }
                    metadata['findings'].append(finding)

                # Check for accessible shares
                share_match = patterns['share'].search(line)
                if share_match and 'READ' in line:
                    ip = share_match.group(1)
                    share = share_match.group(2)

                    # Only report sensitive shares
                    if share in ['ADMIN$', 'C$', 'SYSVOL', 'NETLOGON']:
                        finding = {
                            'title': f"Accessible Share: {share} on {ip}",
                            'severity': 'medium',
                            'description': f"Share {share} is accessible on {ip}",
                            'tool': 'CrackMapExec'
                        }
                        metadata['findings'].append(finding)

            # Build hosts list with pwned status
            for ip in sorted(hosts_set):
                host_data = {
                    'ip': ip,
                    'pwned': ip in pwned_hosts,
                    'source': 'CrackMapExec'
                }
                metadata['hosts'].append(host_data)

            # Update summary
            metadata['summary']['total_hosts'] = len(hosts_set)
            metadata['summary']['total_credentials'] = len(credentials_set)
            metadata['summary']['pwned_hosts'] = len(pwned_hosts)
            metadata['summary']['findings'] = len(metadata['findings'])

            logger.info(
                f"Successfully parsed CrackMapExec log: "
                f"{metadata['summary']['total_hosts']} hosts, "
                f"{metadata['summary']['pwned_hosts']} pwned, "
                f"{metadata['summary']['total_credentials']} credentials"
            )
            return metadata

        except FileNotFoundError:
            logger.error(f"CrackMapExec file not found: {path}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing CrackMapExec file {path}: {e}")
            return None

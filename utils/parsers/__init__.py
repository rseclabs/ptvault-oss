"""
Tool output parsers for PTVault.

This module provides parsers for common penetration testing tools including
Nmap, Burp Suite, Nessus, OWASP ZAP, Qualys, Nuclei, Metasploit, Acunetix,
InsightVM, BloodHound, and CrackMapExec. Each parser extracts structured
metadata from tool output files for storage in the evidence database.
"""

from .base_parser import BaseToolParser
from .nmap_parser import NmapToolParser
from .burp_parser import BurpToolParser
from .nessus_parser import NessusToolParser
from .zap_parser import ZAPParser
from .qualys_parser import QualysParser
from .nuclei_parser import NucleiParser
from .metasploit_parser import MetasploitParser
from .acunetix_parser import AcunetixParser
from .insightvm_parser import InsightVMParser
from .bloodhound_parser import BloodHoundParser
from .crackmapexec_parser import CrackMapExecParser
from .registry import (
    PARSER_REGISTRY,
    get_parser,
    detect_parser,
    list_tools,
    get_tool_info,
    is_tool_supported
)


class ToolParser:
    """
    Base class for tool output parsers.

    DEPRECATED: Use BaseToolParser instead.
    This class is kept for backwards compatibility.
    """

    def validate(self, file_path):
        """
        Validate that the file is the correct format for this parser.

        Args:
            file_path: Path to the file to validate

        Returns:
            bool: True if file is valid for this parser, False otherwise
        """
        raise NotImplementedError("Subclasses must implement validate()")

    def parse(self, file_path):
        """
        Parse the tool output file and extract structured metadata.

        Args:
            file_path: Path to the file to parse

        Returns:
            dict: Structured metadata extracted from the file, or None if parsing fails
        """
        raise NotImplementedError("Subclasses must implement parse()")


__all__ = [
    'BaseToolParser',
    'ToolParser',
    'NmapToolParser',
    'BurpToolParser',
    'NessusToolParser',
    'ZAPParser',
    'QualysParser',
    'NucleiParser',
    'MetasploitParser',
    'AcunetixParser',
    'InsightVMParser',
    'BloodHoundParser',
    'CrackMapExecParser',
    'PARSER_REGISTRY',
    'get_parser',
    'detect_parser',
    'list_tools',
    'get_tool_info',
    'is_tool_supported'
]

"""
Tool parser registry for PTVault.

This module provides a centralized registry for all security tool parsers,
including auto-detection functionality and parser lookup by tool name.
"""

import logging
from typing import Optional, Dict, Type
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

logger = logging.getLogger(__name__)


# Registry mapping tool names to parser classes
PARSER_REGISTRY: Dict[str, Type[BaseToolParser]] = {
    'nmap': NmapToolParser,
    'burp': BurpToolParser,
    'burp_suite': BurpToolParser,
    'nessus': NessusToolParser,
    'zap': ZAPParser,
    'owasp_zap': ZAPParser,
    'qualys': QualysParser,
    'nuclei': NucleiParser,
    'metasploit': MetasploitParser,
    'msf': MetasploitParser,
    'acunetix': AcunetixParser,
    'insightvm': InsightVMParser,
    'nexpose': InsightVMParser,
    'rapid7': InsightVMParser,
    'bloodhound': BloodHoundParser,
    'crackmapexec': CrackMapExecParser,
    'cme': CrackMapExecParser,
}


def get_parser(tool_name: str, file_path: str) -> Optional[BaseToolParser]:
    """
    Get parser instance by tool name.

    Args:
        tool_name: Name of the tool (case-insensitive)
        file_path: Path to the file to parse

    Returns:
        BaseToolParser: Parser instance configured for the file
        None: If tool name is not recognized

    Raises:
        ValueError: If tool name is not in registry

    Example:
        >>> parser = get_parser('nmap', '/path/to/scan.xml')
        >>> if parser:
        ...     data = parser.parse()
    """
    tool_lower = tool_name.lower().strip()

    parser_class = PARSER_REGISTRY.get(tool_lower)

    if not parser_class:
        logger.error(f"Unknown tool name: {tool_name}")
        raise ValueError(f"Unknown tool: {tool_name}. Available tools: {list_tools()}")

    return parser_class(file_path)


def detect_parser(file_path: str) -> Optional[BaseToolParser]:
    """
    Auto-detect which parser to use based on file content.

    Attempts validation with each parser in order until one succeeds.
    Order is optimized for common tools first.

    Args:
        file_path: Path to the file to detect and parse

    Returns:
        BaseToolParser: Parser instance if detected, None otherwise

    Example:
        >>> parser = detect_parser('/path/to/unknown.xml')
        >>> if parser:
        ...     print(f"Detected: {parser.tool_name}")
        ...     data = parser.parse()
    """
    # Order matters - check common tools first
    detection_order = [
        'nmap',
        'burp_suite',
        'nessus',
        'zap',
        'nuclei',
        'qualys',
        'metasploit',
        'acunetix',
        'insightvm',
        'bloodhound',
        'crackmapexec',
    ]

    for tool_name in detection_order:
        parser_class = PARSER_REGISTRY.get(tool_name)
        if not parser_class:
            continue

        try:
            parser = parser_class(file_path)
            if parser.validate():
                logger.info(f"Auto-detected tool: {tool_name} for file: {file_path}")
                return parser
        except Exception as e:
            logger.debug(f"Validation failed for {tool_name}: {e}")
            continue

    logger.warning(f"Could not auto-detect parser for: {file_path}")
    return None


def list_tools() -> list:
    """
    Get list of all supported tool names.

    Returns:
        list: Sorted list of supported tool names
    """
    # Get unique tool names (remove aliases)
    unique_tools = set()
    for tool in PARSER_REGISTRY.keys():
        # Keep primary names only
        if '_' not in tool:
            unique_tools.add(tool)

    return sorted(unique_tools)


def get_tool_info() -> Dict[str, Dict]:
    """
    Get detailed information about all supported tools.

    Returns:
        dict: Dictionary with tool names as keys and info as values
    """
    return {
        'nmap': {
            'name': 'Nmap',
            'description': 'Network scanner - port scanning and service detection',
            'formats': ['XML'],
            'aliases': []
        },
        'burp': {
            'name': 'Burp Suite',
            'description': 'Web application security scanner',
            'formats': ['XML'],
            'aliases': ['burp_suite']
        },
        'nessus': {
            'name': 'Nessus',
            'description': 'Vulnerability scanner',
            'formats': ['XML (.nessus)'],
            'aliases': []
        },
        'zap': {
            'name': 'OWASP ZAP',
            'description': 'Web application security scanner',
            'formats': ['XML'],
            'aliases': ['owasp_zap']
        },
        'qualys': {
            'name': 'Qualys',
            'description': 'Vulnerability management platform',
            'formats': ['XML'],
            'aliases': []
        },
        'nuclei': {
            'name': 'Nuclei',
            'description': 'Fast template-based vulnerability scanner',
            'formats': ['JSON', 'JSONL'],
            'aliases': []
        },
        'metasploit': {
            'name': 'Metasploit Framework',
            'description': 'Penetration testing framework',
            'formats': ['XML (workspace export)'],
            'aliases': ['msf']
        },
        'acunetix': {
            'name': 'Acunetix',
            'description': 'Web vulnerability scanner',
            'formats': ['XML'],
            'aliases': []
        },
        'insightvm': {
            'name': 'Rapid7 InsightVM',
            'description': 'Vulnerability management (formerly Nexpose)',
            'formats': ['XML'],
            'aliases': ['nexpose', 'rapid7']
        },
        'bloodhound': {
            'name': 'BloodHound',
            'description': 'Active Directory attack path analysis',
            'formats': ['JSON'],
            'aliases': []
        },
        'crackmapexec': {
            'name': 'CrackMapExec',
            'description': 'Network pentesting and lateral movement',
            'formats': ['Log files'],
            'aliases': ['cme']
        },
    }


def is_tool_supported(tool_name: str) -> bool:
    """
    Check if a tool name is supported.

    Args:
        tool_name: Tool name to check (case-insensitive)

    Returns:
        bool: True if tool is supported, False otherwise
    """
    return tool_name.lower().strip() in PARSER_REGISTRY

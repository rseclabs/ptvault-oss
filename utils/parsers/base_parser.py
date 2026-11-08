"""
Base parser class for security tool output parsers.

This module provides an abstract base class that all tool parsers extend.
It defines the standard interface and common utility methods for parsing
security tool outputs into structured PTVault data.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class BaseToolParser(ABC):
    """
    Abstract base class for all security tool parsers.

    All parsers must implement validate() and parse() methods.
    Provides common utility methods for data normalization and extraction.
    """

    def __init__(self, file_path: Optional[str] = None):
        """
        Initialize parser. file_path may be supplied at construction
        (registry pattern) or passed to parse()/validate() (legacy pattern).

        Args:
            file_path: Path to the tool output file to parse
        """
        self.file_path = file_path
        self.tool_name = self.__class__.__name__.replace('Parser', '').replace('Tool', '')

    @abstractmethod
    def validate(self, file_path: Optional[str] = None) -> bool:
        """
        Validate that the file is correct format for this parser.

        Args:
            file_path: Optional path to validate (uses self.file_path if not provided)

        Returns:
            bool: True if file is valid for this parser, False otherwise
        """
        pass

    @abstractmethod
    def parse(self, file_path: Optional[str] = None) -> Optional[Dict]:
        """
        Parse tool output and return structured data.

        Args:
            file_path: Optional path to parse (uses self.file_path if not provided)

        Returns:
            dict: Structured data with keys:
                - tool: str (tool name)
                - hosts: List[Dict] (host information)
                - findings: List[Dict] (vulnerability findings)
                - credentials: List[Dict] (discovered credentials)
                - metadata: Dict (scan metadata)
            None if parsing fails
        """
        pass

    def extract_hosts(self, data) -> List[Dict]:
        """
        Extract host information from parsed data.

        Override this method to extract hosts from tool-specific data.

        Args:
            data: Tool-specific parsed data

        Returns:
            List[Dict]: List of host dictionaries with keys:
                - ip: str (IP address)
                - hostname: str (optional)
                - os: str (optional)
                - source: str (tool name)
        """
        return []

    def extract_findings(self, data) -> List[Dict]:
        """
        Extract vulnerability findings from parsed data.

        Override this method to extract findings from tool-specific data.

        Args:
            data: Tool-specific parsed data

        Returns:
            List[Dict]: List of finding dictionaries with keys:
                - title: str
                - severity: str (critical, high, medium, low, info)
                - description: str
                - solution: str (optional)
                - tool: str (tool name)
        """
        return []

    def extract_credentials(self, data) -> List[Dict]:
        """
        Extract discovered credentials from parsed data.

        Override this method to extract credentials from tool-specific data.

        Args:
            data: Tool-specific parsed data

        Returns:
            List[Dict]: List of credential dictionaries with keys:
                - username: str
                - password: str (optional)
                - hash: str (optional)
                - service: str (optional)
                - domain: str (optional)
        """
        return []

    @staticmethod
    def to_port(value) -> Optional[int]:
        """A port number (0-65535) or None; scan files are untrusted (H-13)."""
        try:
            port = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return port if 0 <= port <= 65535 else None

    @staticmethod
    def to_score(value) -> Optional[float]:
        """A CVSS score (0.0-10.0) or None; scan files are untrusted (H-13)."""
        try:
            score = float(str(value).strip())
        except (TypeError, ValueError):
            return None
        return score if 0.0 <= score <= 10.0 else None   # NaN and inf fail both comparisons

    def normalize_severity(self, severity: str) -> str:
        """
        Normalize severity levels to PTVault standard.

        Maps various severity naming conventions to:
        critical, high, medium, low, info

        Args:
            severity: Original severity string from tool

        Returns:
            str: Normalized severity level
        """
        if not severity:
            return 'medium'

        severity_lower = severity.lower()

        # Critical level mappings
        if severity_lower in ['critical', '4', 'very high']:
            return 'critical'

        # High level mappings
        if severity_lower in ['high', '3', 'important']:
            return 'high'

        # Medium level mappings
        if severity_lower in ['medium', 'moderate', '2']:
            return 'medium'

        # Low level mappings
        if severity_lower in ['low', 'minor', '1']:
            return 'low'

        # Info level mappings
        if severity_lower in ['info', 'informational', 'information', '0', 'note']:
            return 'info'

        # Default to medium if unrecognized
        logger.warning(f"Unknown severity '{severity}', defaulting to 'medium'")
        return 'medium'

    def extract_host_from_url(self, url: str) -> Optional[str]:
        """
        Extract hostname or IP from a URL.

        Args:
            url: Full URL string

        Returns:
            str: Hostname or IP address, or None if extraction fails
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc or parsed.path.split('/')[0]
        except Exception as e:
            logger.warning(f"Failed to extract host from URL '{url}': {e}")
            return None

    def safe_get(self, data: Dict, key: str, default=None):
        """
        Safely get value from dictionary.

        Args:
            data: Dictionary to query
            key: Key to retrieve
            default: Default value if key not found

        Returns:
            Value from dictionary or default
        """
        try:
            return data.get(key, default)
        except (AttributeError, TypeError):
            return default

    def safe_text(self, element, default: str = "") -> str:
        """
        Safely extract text from XML element.

        Args:
            element: XML element or None
            default: Default value if element is None or has no text

        Returns:
            str: Element text or default value
        """
        try:
            if element is None:
                return default
            text = element.text
            return text if text else default
        except AttributeError:
            return default

    def filter_none(self, data: Dict) -> Dict:
        """
        Remove None values from dictionary.

        Args:
            data: Dictionary with potential None values

        Returns:
            Dict: Dictionary with None values removed
        """
        return {k: v for k, v in data.items() if v is not None}

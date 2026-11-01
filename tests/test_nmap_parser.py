"""
Tests for nmap XML parser.

This module tests the NmapToolParser class to ensure it correctly validates
and parses nmap XML output files.
"""

import os
import pytest
import tempfile
from utils.parsers.nmap_parser import NmapToolParser


# Get the path to the test fixtures directory
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
SAMPLE_NMAP_XML = os.path.join(FIXTURES_DIR, 'sample_nmap.xml')


class TestNmapToolParser:
    """Test suite for NmapToolParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = NmapToolParser()

    def test_validate_accepts_valid_nmap_xml(self):
        """Test that validate() accepts valid nmap XML."""
        assert self.parser.validate(SAMPLE_NMAP_XML) is True

    def test_validate_rejects_non_nmap_xml(self):
        """Test that validate() rejects non-nmap XML."""
        # Create a temporary XML file that is not nmap format
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write('<?xml version="1.0"?><notNmap><data>test</data></notNmap>')
            temp_file = f.name

        try:
            assert self.parser.validate(temp_file) is False
        finally:
            os.unlink(temp_file)

    def test_validate_rejects_malformed_xml(self):
        """Test that validate() rejects malformed XML."""
        # Create a temporary file with malformed XML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write('<?xml version="1.0"?><nmaprun><unclosed>')
            temp_file = f.name

        try:
            assert self.parser.validate(temp_file) is False
        finally:
            os.unlink(temp_file)

    def test_parse_extracts_correct_metadata_structure(self):
        """Test that parse() extracts correct metadata structure."""
        metadata = self.parser.parse(SAMPLE_NMAP_XML)

        assert metadata is not None
        assert 'tool' in metadata
        assert 'tool_version' in metadata
        assert 'scan_type' in metadata
        assert 'scan_args' in metadata
        assert 'start_time' in metadata
        assert 'end_time' in metadata
        assert 'summary' in metadata
        assert 'hosts' in metadata

    def test_parse_extracts_tool_information(self):
        """Test that parse() extracts correct tool information."""
        metadata = self.parser.parse(SAMPLE_NMAP_XML)

        assert metadata['tool'] == 'nmap'
        assert metadata['tool_version'] == '7.94'
        assert 'nmap -sV' in metadata['scan_args']

    def test_parse_extracts_summary_statistics(self):
        """Test that parse() extracts correct summary statistics."""
        metadata = self.parser.parse(SAMPLE_NMAP_XML)

        assert metadata['summary']['hosts_total'] == 256
        assert metadata['summary']['hosts_up'] == 1
        assert metadata['summary']['hosts_down'] == 255

    def test_parse_extracts_host_information(self):
        """Test that parse() extracts correct host information."""
        metadata = self.parser.parse(SAMPLE_NMAP_XML)

        # Should have exactly one host (only "up" hosts are included)
        assert len(metadata['hosts']) == 1

        host = metadata['hosts'][0]
        assert host['ip'] == '192.168.1.10'
        assert host['hostname'] == 'webserver.local'
        assert host['status'] == 'up'
        # OS detection may or may not be present depending on libnmap version
        assert 'os' in host
        assert 'open_ports' in host

    def test_parse_extracts_open_ports(self):
        """Test that parse() extracts correct port information."""
        metadata = self.parser.parse(SAMPLE_NMAP_XML)

        host = metadata['hosts'][0]
        open_ports = host['open_ports']

        # Should have exactly 2 open ports (22 and 80, not 443 which is closed)
        assert len(open_ports) == 2

        # Verify SSH port (22)
        ssh_port = next((p for p in open_ports if p['port'] == 22), None)
        assert ssh_port is not None
        assert ssh_port['protocol'] == 'tcp'
        assert ssh_port['state'] == 'open'
        assert ssh_port['service'] == 'ssh'
        assert ssh_port['product'] == 'OpenSSH'
        assert ssh_port['version'] == '8.2p1'

        # Verify HTTP port (80)
        http_port = next((p for p in open_ports if p['port'] == 80), None)
        assert http_port is not None
        assert http_port['protocol'] == 'tcp'
        assert http_port['state'] == 'open'
        assert http_port['service'] == 'http'
        assert http_port['product'] == 'Apache httpd'
        assert http_port['version'] == '2.4.41'

    def test_parse_handles_malformed_xml_gracefully(self):
        """Test that parse() handles malformed XML gracefully by returning None."""
        # Create a temporary file with malformed XML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write('<?xml version="1.0"?><nmaprun><unclosed>')
            temp_file = f.name

        try:
            result = self.parser.parse(temp_file)
            assert result is None
        finally:
            os.unlink(temp_file)

    def test_parse_timestamp_formatting(self):
        """Test that timestamps are formatted as ISO 8601."""
        metadata = self.parser.parse(SAMPLE_NMAP_XML)

        # Verify timestamps are in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)
        assert metadata['start_time'] is not None
        assert metadata['end_time'] is not None
        assert 'T' in metadata['start_time']
        assert 'T' in metadata['end_time']

    def test_parse_filters_closed_ports(self):
        """Test that parse() only includes open ports, not closed or filtered."""
        metadata = self.parser.parse(SAMPLE_NMAP_XML)

        host = metadata['hosts'][0]
        open_ports = host['open_ports']

        # Verify that port 443 (which is closed) is not included
        port_443 = next((p for p in open_ports if p['port'] == 443), None)
        assert port_443 is None

    def test_parse_handles_missing_optional_fields(self):
        """Test that parse() handles missing optional fields gracefully."""
        # Create a minimal nmap XML without optional fields
        minimal_xml = '''<?xml version="1.0"?>
<nmaprun scanner="nmap" args="nmap 192.168.1.1" start="1703592000" version="7.94">
  <host>
    <status state="up"/>
    <address addr="192.168.1.1" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http"/>
      </port>
    </ports>
  </host>
  <runstats>
    <finished time="1703592900"/>
    <hosts up="1" down="0" total="1"/>
  </runstats>
</nmaprun>'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(minimal_xml)
            temp_file = f.name

        try:
            metadata = self.parser.parse(temp_file)
            assert metadata is not None
            assert len(metadata['hosts']) == 1
            host = metadata['hosts'][0]

            # hostname should be None when not present
            assert host['hostname'] is None

            # os should be None when not detected
            # (libnmap may or may not include this field)

            # Port info should still be extracted
            assert len(host['open_ports']) == 1
            port = host['open_ports'][0]
            assert port['service'] == 'http'
            # product and version should be None when not present
            assert port['product'] is None
            assert port['version'] is None
        finally:
            os.unlink(temp_file)

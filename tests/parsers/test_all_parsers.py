"""
Comprehensive tests for all security tool parsers.

Tests validation, parsing, and data extraction for all supported parsers.
"""

import pytest
import json
import os
from pathlib import Path

# Import all parsers
from utils.parsers import (
    BaseToolParser,
    NmapToolParser,
    BurpToolParser,
    NessusToolParser,
    ZAPParser,
    QualysParser,
    NucleiParser,
    MetasploitParser,
    AcunetixParser,
    InsightVMParser,
    BloodHoundParser,
    CrackMapExecParser,
    get_parser,
    detect_parser,
    list_tools,
    is_tool_supported
)


# Fixtures directory
FIXTURES_DIR = Path(__file__).parent.parent / 'fixtures' / 'parsers'


class TestParserRegistry:
    """Test parser registry functions."""

    def test_list_tools(self):
        """Test listing all available tools."""
        tools = list_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 11  # At least 11 tools
        assert 'nmap' in tools
        assert 'zap' in tools
        assert 'nuclei' in tools

    def test_is_tool_supported(self):
        """Test tool support checking."""
        assert is_tool_supported('nmap')
        assert is_tool_supported('NMAP')  # Case insensitive
        assert is_tool_supported('zap')
        assert is_tool_supported('nuclei')
        assert not is_tool_supported('unknown_tool')

    def test_get_parser_valid_tool(self, tmp_path):
        """Test getting parser by name."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<nmaprun></nmaprun>")

        parser = get_parser('nmap', str(test_file))
        assert parser is not None
        assert isinstance(parser, NmapToolParser)

    def test_get_parser_invalid_tool(self, tmp_path):
        """Test getting parser with invalid tool name."""
        test_file = tmp_path / "test.xml"
        test_file.write_text("<test></test>")

        with pytest.raises(ValueError):
            get_parser('invalid_tool', str(test_file))


class TestBaseParser:
    """Test base parser utility methods."""

    def test_normalize_severity(self):
        """Test severity normalization."""
        parser = NmapToolParser('/fake/path')

        assert parser.normalize_severity('critical') == 'critical'
        assert parser.normalize_severity('CRITICAL') == 'critical'
        assert parser.normalize_severity('4') == 'critical'
        assert parser.normalize_severity('high') == 'high'
        assert parser.normalize_severity('3') == 'high'
        assert parser.normalize_severity('medium') == 'medium'
        assert parser.normalize_severity('2') == 'medium'
        assert parser.normalize_severity('low') == 'low'
        assert parser.normalize_severity('1') == 'low'
        assert parser.normalize_severity('info') == 'info'
        assert parser.normalize_severity('informational') == 'info'
        assert parser.normalize_severity('0') == 'info'
        assert parser.normalize_severity('unknown') == 'medium'  # Default

    def test_extract_host_from_url(self):
        """Test URL host extraction."""
        parser = NmapToolParser('/fake/path')

        assert parser.extract_host_from_url('http://example.com/path') == 'example.com'
        assert parser.extract_host_from_url('https://example.com:8443/path') == 'example.com:8443'
        assert parser.extract_host_from_url('http://192.168.1.1/') == '192.168.1.1'

    def test_filter_none(self):
        """Test None value filtering."""
        parser = NmapToolParser('/fake/path')

        data = {
            'key1': 'value1',
            'key2': None,
            'key3': 'value3',
            'key4': None
        }

        filtered = parser.filter_none(data)

        assert 'key1' in filtered
        assert 'key2' not in filtered
        assert 'key3' in filtered
        assert 'key4' not in filtered


class TestZAPParser:
    """Test OWASP ZAP parser."""

    def test_validate_valid_zap_file(self, tmp_path):
        """Test validation with valid ZAP XML."""
        zap_file = tmp_path / "zap.xml"
        zap_file.write_text("""<?xml version="1.0"?>
<OWASPZAPReport version="2.11.0" generated="2024-01-01">
    <site name="http://example.com">
        <alerts>
            <alertitem>
                <name>SQL Injection</name>
                <riskcode>3</riskcode>
                <desc>SQL injection found</desc>
            </alertitem>
        </alerts>
    </site>
</OWASPZAPReport>""")

        parser = ZAPParser(str(zap_file))
        assert parser.validate()

    def test_validate_invalid_file(self, tmp_path):
        """Test validation with invalid XML."""
        invalid_file = tmp_path / "invalid.xml"
        invalid_file.write_text("<notZAP></notZAP>")

        parser = ZAPParser(str(invalid_file))
        assert not parser.validate()


class TestQualysParser:
    """Test Qualys parser."""

    def test_validate_valid_qualys_file(self, tmp_path):
        """Test validation with valid Qualys XML."""
        qualys_file = tmp_path / "qualys.xml"
        qualys_file.write_text("""<?xml version="1.0"?>
<SCAN>
    <HEADER>
        <DATETIME>2024-01-01</DATETIME>
    </HEADER>
</SCAN>""")

        parser = QualysParser(str(qualys_file))
        assert parser.validate()

    def test_validate_asset_data_report(self, tmp_path):
        """Test validation with ASSET_DATA_REPORT format."""
        qualys_file = tmp_path / "qualys_assets.xml"
        qualys_file.write_text("""<?xml version="1.0"?>
<ASSET_DATA_REPORT>
    <HEADER>
        <DATETIME>2024-01-01</DATETIME>
    </HEADER>
</ASSET_DATA_REPORT>""")

        parser = QualysParser(str(qualys_file))
        assert parser.validate()


class TestNucleiParser:
    """Test Nuclei parser."""

    def test_validate_valid_nuclei_json(self, tmp_path):
        """Test validation with valid Nuclei JSON."""
        nuclei_file = tmp_path / "nuclei.json"
        nuclei_file.write_text(json.dumps({
            "template-id": "cve-2021-1234",
            "info": {
                "name": "Test Vulnerability",
                "severity": "high"
            },
            "host": "http://example.com"
        }))

        parser = NucleiParser(str(nuclei_file))
        assert parser.validate()

    def test_validate_valid_nuclei_jsonl(self, tmp_path):
        """Test validation with Nuclei JSONL format."""
        nuclei_file = tmp_path / "nuclei.jsonl"
        nuclei_file.write_text('{"template-id": "test1", "host": "example.com"}')

        parser = NucleiParser(str(nuclei_file))
        assert parser.validate()

    def test_parse_nuclei_json(self, tmp_path):
        """Test parsing Nuclei JSON output."""
        nuclei_file = tmp_path / "nuclei.json"
        data = [
            {
                "template-id": "cve-2021-1234",
                "info": {
                    "name": "SQL Injection",
                    "severity": "high",
                    "description": "SQL injection vulnerability"
                },
                "host": "http://example.com",
                "matched-at": "http://example.com/login"
            },
            {
                "template-id": "exposed-admin",
                "info": {
                    "name": "Exposed Admin Panel",
                    "severity": "medium"
                },
                "host": "http://example.com"
            }
        ]
        nuclei_file.write_text(json.dumps(data))

        parser = NucleiParser(str(nuclei_file))
        result = parser.parse()

        assert result is not None
        assert result['tool'] == 'nuclei'
        assert len(result['findings']) == 2
        assert result['summary']['total_findings'] == 2
        assert len(result['hosts']) >= 1


class TestMetasploitParser:
    """Test Metasploit parser."""

    def test_validate_valid_metasploit_file(self, tmp_path):
        """Test validation with valid Metasploit XML."""
        msf_file = tmp_path / "metasploit.xml"
        msf_file.write_text("""<?xml version="1.0"?>
<MetasploitV4>
    <workspace>
        <name>Test Workspace</name>
    </workspace>
    <hosts>
        <host>
            <address>192.168.1.1</address>
        </host>
    </hosts>
</MetasploitV4>""")

        parser = MetasploitParser(str(msf_file))
        assert parser.validate()


class TestAcunetixParser:
    """Test Acunetix parser."""

    def test_validate_valid_acunetix_file(self, tmp_path):
        """Test validation with valid Acunetix XML."""
        acunetix_file = tmp_path / "acunetix.xml"
        acunetix_file.write_text("""<?xml version="1.0"?>
<ScanGroup>
    <Scan>
        <StartTime>2024-01-01</StartTime>
    </Scan>
</ScanGroup>""")

        parser = AcunetixParser(str(acunetix_file))
        assert parser.validate()


class TestInsightVMParser:
    """Test InsightVM parser."""

    def test_validate_valid_insightvm_file(self, tmp_path):
        """Test validation with valid InsightVM XML."""
        insightvm_file = tmp_path / "insightvm.xml"
        insightvm_file.write_text("""<?xml version="1.0"?>
<NexposeReport name="Test Scan" generated="2024-01-01">
    <nodes>
        <node address="192.168.1.1">
        </node>
    </nodes>
</NexposeReport>""")

        parser = InsightVMParser(str(insightvm_file))
        assert parser.validate()


class TestBloodHoundParser:
    """Test BloodHound parser."""

    def test_validate_valid_bloodhound_file(self, tmp_path):
        """Test validation with valid BloodHound JSON."""
        bh_file = tmp_path / "bloodhound.json"
        bh_file.write_text(json.dumps({
            "data": {
                "computers": [],
                "users": [],
                "groups": []
            }
        }))

        parser = BloodHoundParser(str(bh_file))
        assert parser.validate()

    def test_parse_bloodhound_json(self, tmp_path):
        """Test parsing BloodHound JSON output."""
        bh_file = tmp_path / "bloodhound.json"
        data = {
            "data": {
                "computers": [
                    {
                        "ObjectIdentifier": "S-1-5-21-123456",
                        "Properties": {
                            "name": "DESKTOP-ABC123.domain.com",
                            "ipaddress": "192.168.1.10",
                            "operatingsystem": "Windows 10",
                            "enabled": True,
                            "highvalue": False
                        }
                    }
                ],
                "users": [
                    {
                        "ObjectIdentifier": "S-1-5-21-789012",
                        "Properties": {
                            "name": "ADMIN@DOMAIN.COM",
                            "enabled": True,
                            "admincount": True,
                            "highvalue": True
                        }
                    }
                ],
                "groups": []
            }
        }
        bh_file.write_text(json.dumps(data))

        parser = BloodHoundParser(str(bh_file))
        result = parser.parse()

        assert result is not None
        assert result['tool'] == 'bloodhound'
        assert result['summary']['total_computers'] == 1
        assert result['summary']['total_users'] == 1
        assert result['summary']['high_value_targets'] == 1
        assert len(result['hosts']) == 1


class TestCrackMapExecParser:
    """Test CrackMapExec parser."""

    def test_validate_valid_cme_log(self, tmp_path):
        """Test validation with valid CME log."""
        cme_file = tmp_path / "cme.log"
        cme_file.write_text("""[SMB] 192.168.1.10 - Windows 10
[SMB] 192.168.1.10 - domain\\admin:password123 (Pwn3d!)
""")

        parser = CrackMapExecParser(str(cme_file))
        assert parser.validate()

    def test_parse_cme_log(self, tmp_path):
        """Test parsing CME log output."""
        cme_file = tmp_path / "cme.log"
        log_content = """[SMB] 192.168.1.10 - Windows 10
[SMB] 192.168.1.10 - domain\\admin:password123 (Pwn3d!)
[SMB] 192.168.1.11 - Windows Server 2019
[SMB] 192.168.1.10 - Dumping SAM hashes
[SMB] 192.168.1.10 - [ADMIN$] READ
"""
        cme_file.write_text(log_content)

        parser = CrackMapExecParser(str(cme_file))
        result = parser.parse()

        assert result is not None
        assert result['tool'] == 'crackmapexec'
        assert result['summary']['total_hosts'] >= 2
        assert result['summary']['pwned_hosts'] >= 1
        assert result['summary']['total_credentials'] >= 1
        assert len(result['findings']) >= 1


class TestParserAutoDetection:
    """Test automatic parser detection."""

    def test_detect_nmap_file(self, tmp_path):
        """Test auto-detection of Nmap file."""
        nmap_file = tmp_path / "scan.xml"
        nmap_file.write_text("""<?xml version="1.0"?>
<nmaprun scanner="nmap" version="7.80">
</nmaprun>""")

        parser = detect_parser(str(nmap_file))
        assert parser is not None
        assert isinstance(parser, NmapToolParser)

    def test_detect_zap_file(self, tmp_path):
        """Test auto-detection of ZAP file."""
        zap_file = tmp_path / "zap.xml"
        zap_file.write_text("""<?xml version="1.0"?>
<OWASPZAPReport version="2.11.0">
</OWASPZAPReport>""")

        parser = detect_parser(str(zap_file))
        assert parser is not None
        assert isinstance(parser, ZAPParser)

    def test_detect_nuclei_file(self, tmp_path):
        """Test auto-detection of Nuclei file."""
        nuclei_file = tmp_path / "nuclei.json"
        nuclei_file.write_text(json.dumps({
            "template-id": "test",
            "host": "example.com"
        }))

        parser = detect_parser(str(nuclei_file))
        assert parser is not None
        assert isinstance(parser, NucleiParser)

    def test_detect_unknown_file(self, tmp_path):
        """Test auto-detection with unknown file format."""
        unknown_file = tmp_path / "unknown.txt"
        unknown_file.write_text("This is not a known tool format")

        parser = detect_parser(str(unknown_file))
        assert parser is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

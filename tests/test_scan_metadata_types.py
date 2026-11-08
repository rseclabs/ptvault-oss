"""H-13 (server side): scan parsers store ports and CVSS scores as numbers.

The Vulnerabilities tab renders straight from evidence metadata, so a crafted
scan file must not be able to put markup in fields that are numbers.
"""

from utils.parsers import BurpToolParser, NessusToolParser
from utils.parsers.base_parser import BaseToolParser

PAYLOAD = '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'

NESSUS = f"""<?xml version="1.0"?>
<NessusClientData_v2><Report name="r"><ReportHost name="10.0.0.9"><HostProperties/>
<ReportItem port="{PAYLOAD}" protocol="tcp" severity="3" pluginID="1" pluginName="n">
  <cvss_base_score>{PAYLOAD}</cvss_base_score>
</ReportItem>
<ReportItem port="443" protocol="tcp" severity="3" pluginID="2" pluginName="ok">
  <cvss_base_score>7.5</cvss_base_score>
</ReportItem>
</ReportHost></Report></NessusClientData_v2>"""


def test_nessus_port_and_cvss_are_numbers(tmp_path):
    path = tmp_path / 'scan.nessus'
    path.write_text(NESSUS)
    vulns = NessusToolParser(str(path)).parse()['hosts'][0]['vulnerabilities']
    assert (vulns[0]['port'], vulns[0]['cvss_base_score']) == (None, None)
    assert (vulns[1]['port'], vulns[1]['cvss_base_score']) == (443, 7.5)


def test_number_helpers():
    assert [BaseToolParser.to_port(v) for v in ('80', 443, '0', '65536', '-1', 'x', None, '8080 ')] == \
        [80, 443, 0, None, None, None, None, 8080]
    assert [BaseToolParser.to_score(v) for v in ('9.8', 10, '10.1', '-1', 'nan', 'inf', 'x', None)] == \
        [9.8, 10.0, None, None, None, None, None, None]

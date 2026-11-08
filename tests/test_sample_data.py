"""Consistency checks for the shipped sample engagement (sample_data/).

load_sample.py talks to a running PTVault, so it is not run here. These tests
catch the mistakes an edit to sample_data/content.py usually makes: a host IP
that no scan creates, a key that points at nothing, a value the API rejects,
or a tool file the parsers no longer read.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from utils.helpers import HOST_COLORS
from utils.parsers.burp_parser import BurpToolParser
from utils.parsers.nessus_parser import NessusToolParser
from utils.parsers.nmap_parser import NmapToolParser

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data"
FILES = SAMPLE / "files"


@pytest.fixture(scope="module")
def C():
    spec = importlib.util.spec_from_file_location("sample_content", SAMPLE / "content.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def nmap():
    return NmapToolParser().parse(str(FILES / "acme_internal_nmap.xml"))


def _ip(host):
    return host.get("ip") or host.get("address")


def test_tool_files_parse(nmap):
    assert len(nmap["hosts"]) == 20
    nessus = NessusToolParser().parse(str(FILES / "acme_internal.nessus"))
    assert nessus and nessus.get("hosts")
    burp = BurpToolParser().parse(str(FILES / "acme_intranet_burp.xml"))
    assert burp["summary"]["total_issues"] == 6


def test_every_referenced_file_exists(C):
    names = [f for f, *_ in C.TOOL_IMPORTS] + [e["file"] for e in C.EVIDENCE if e.get("file")]
    names.append(C.ATTACK_LAYER_FILE)
    for name in names:
        assert (FILES / name).is_file(), name
    layer = json.loads((FILES / C.ATTACK_LAYER_FILE).read_text())
    assert layer["techniques"]


def test_every_host_ip_is_created(C, nmap):
    known = {_ip(h) for h in nmap["hosts"]} | {h["ip"] for h in C.MANUAL_HOSTS}
    used = set(C.HOST_STATUS) | set(C.HOST_NOTES) | set(C.HOST_CREDENTIALS)
    used |= {ip for e in C.EVIDENCE for ip in e.get("hosts", [])}
    used |= {n[5]["ref"] for n in C.ATTACK_MAP["nodes"] if n[1] == "host_ref"}
    assert used <= known, used - known


def test_keys_resolve(C):
    findings = {f["key"] for f in C.FINDINGS}
    evidence = {e["key"] for e in C.EVIDENCE}
    notes = {n[0] for n in C.ENGAGEMENT_NOTES}
    creds = {c["username"].split("\\")[-1] for cs in C.HOST_CREDENTIALS.values() for c in cs}
    pools = {"finding": findings, "evidence": evidence, "note": notes, "credential": creds}
    for src, dst, rtype, _label in C.RELATIONSHIPS:
        assert src[1] in pools[src[0]] and dst[1] in pools[dst[0]], (src, dst)
        assert rtype in {"leads_to", "uses", "discovers", "exploits", "escalates", "custom"}
    assert {C.SAVED_PATH["start"], C.SAVED_PATH["end"]} <= evidence
    for _key, _title, parent, _body in C.ENGAGEMENT_NOTES:
        assert parent is None or parent in notes
    node_keys = {n[0] for n in C.ATTACK_MAP["nodes"]}
    for src, dst, _ in C.ATTACK_MAP["edges"]:
        assert src in node_keys and dst in node_keys
    for _key, ntype, *_rest, props in C.ATTACK_MAP["nodes"]:
        assert ntype in {"recon", "tactic", "exploit", "connector", "host_ref", "finding_ref", "evidence_ref"}
        if ntype == "finding_ref":
            assert props["ref"] in findings
        if ntype == "evidence_ref":
            assert props["ref"] in evidence
    for item in C.REPORT:
        if item[0] == "finding":
            assert item[1] in findings
        if item[0] == "writeup":
            assert item[1] in {w["name"] for w in C.WRITEUPS}
    shots = [part.split("}}")[0] for notes_ in C.HOST_NOTES.values() for _t, body in notes_
             for part in body.split("{{shot:")[1:]]
    assert shots and set(shots) <= evidence


def test_values_the_api_accepts(C):
    for status in C.HOST_STATUS.values():
        assert status.get("color_category") in HOST_COLORS | {None}
    for f in C.FINDINGS:
        assert f["criticality"] in {"critical", "high", "medium", "low"}
    for c in C.ENGAGEMENT_CREDENTIALS:
        assert c["credential_type"] in {"clear_text", "ntlm", "ntlmv2", "krbtgt", "md5", "sha"}
    for cs in C.HOST_CREDENTIALS.values():
        for c in cs:
            assert c["password_type"] in {"cleartext", "hash"}
    for e in C.EVIDENCE:
        assert e["evidence_type"] in {"note", "command_output", "screenshot", "tool_output", "other"}
    for cmd in C.COMMANDS:
        assert cmd["category"] in {"Recon", "Enumeration", "Exploitation", "Post-exploitation", "Reporting"}
    for it in C.TEST_PLAN["items"]:
        assert it["result"]["status"] in {"pending", "in_progress", "completed", "failed", "skipped"}
        assert it["result"].get("outcome") in {"prevented", "alerted", "logged", "not_detected", None}


def test_sample_stays_fictional(C, nmap):
    """Addresses stay in 10.0.5.0/24 and names in acme.local / acme.example."""
    for h in nmap["hosts"]:
        assert _ip(h).startswith("10.0.5.")
    text = (SAMPLE / "content.py").read_text()
    for domain in ("acme.com", "@gmail", "@outlook"):
        assert domain not in text

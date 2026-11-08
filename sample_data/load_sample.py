#!/usr/bin/env python3
"""Load the PTVault sample engagement into a running PTVault instance.

The sample is a fictional internal penetration test of "ACME Corporation"
that touches every part of the app: imported Nmap/Nessus/Burp output, hosts
with indicators, ports, notes and credentials, screenshots and other
evidence, findings, relationships, an attack map, saved filters, an ATT&CK
layer, a test plan with recorded executions, writeups, commands, and a
finished report. See sample_data/README.md for a guided tour.

It talks to PTVault only through its normal REST API, as the logged-in user,
so it works with an encrypted database and never touches the data folder.
It needs only the Python standard library.

Usage (PTVault running and unlocked):
    python3 sample_data/load_sample.py --email admin@example.com
    python3 sample_data/load_sample.py --url http://localhost:5000 --email admin@example.com --replace

The password is read from the PTVAULT_PASSWORD environment variable, or
prompted for. Use an admin or tester account.
"""

import argparse
import getpass
import http.cookiejar
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = HERE / "files"
sys.path.insert(0, str(HERE))
import content as C  # noqa: E402


class ApiError(RuntimeError):
    pass


class Client:
    """Minimal PTVault API client: cookie session plus double-submit CSRF."""

    def __init__(self, base_url):
        self.base = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _csrf(self):
        for c in self.jar:
            if c.name == "csrf_token":
                return c.value
        return None

    def request(self, method, path, body=None, files=None, ok=(200, 201, 204)):
        headers = {"Accept": "application/json"}
        data = None
        if files is not None:
            data, ctype = _multipart(body or {}, files)
            headers["Content-Type"] = ctype
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if method != "GET" and self._csrf():
            headers["X-CSRF-Token"] = self._csrf()
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=120) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except urllib.error.URLError as e:
            raise ApiError(f"cannot reach {self.base}: {e.reason}") from None
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = None
        if status not in ok:
            msg = payload.get("error") if isinstance(payload, dict) else raw[:200].decode(errors="replace")
            raise ApiError(f"{method} {path} -> {status}: {msg}")
        return payload

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body, **kw)

    def put(self, path, body=None, **kw):
        return self.request("PUT", path, body, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)

    def login(self, email, password):
        self.get("/api/auth/csrf-token")
        try:
            self.post("/api/auth/login", {"email": email, "password": password})
        except ApiError as e:
            if " 423" in str(e) or "locked" in str(e).lower():
                raise ApiError("PTVault is locked: open it in a browser, unlock it, then rerun") from None
            raise
        self.get("/api/auth/csrf-token")  # the token is bound to the new session


def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    out = bytearray()
    for name, value in fields.items():
        if value is None:
            continue
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        out += str(value).encode() + b"\r\n"
    for name, path in files.items():
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{path.name}"\r\nContent-Type: {ctype}\r\n\r\n').encode()
        out += path.read_bytes() + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def items(payload, *keys):
    """Return the list from a response that is either a list or {key: [...]}."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in keys:
            if isinstance(payload.get(k), list):
                return payload[k]
    return []


# Report builder format tools and their display titles (formatToolMeta in static/js/reporting.js).
TOOL_TITLES = {
    "spacer": "Spacer", "divider": "Divider", "pagebreak": "Page Break", "sectionheader": "Section Header",
    "textblock": "Text Block", "quote": "Quote Block", "bulletlist": "Bullet List",
    "numberedlist": "Numbered List", "checklist": "Checklist", "codeblock": "Code Block",
    "commandoutput": "Command Output", "alertbox": "Alert Box", "keyfinding": "Key Finding",
    "evidence": "Evidence Block", "imageplaceholder": "Image Placeholder", "table": "Table",
    "twocolumn": "Two-Column", "timeline": "Timeline", "riskmatrix": "Risk Matrix", "cvsscard": "CVSS Card",
    "attackmap": "Attack Map", "coloredtable": "Findings Table",
}


def step(msg):
    print(f"  - {msg}")


# ---------------------------------------------------------------------------
# Removing an earlier copy
# ---------------------------------------------------------------------------
def find_sample(api):
    for e in items(api.get("/api/engagements"), "engagements"):
        if e.get("short_name") == C.SHORT_NAME:
            return e
    return None


def remove_sample(api, eng):
    """Delete the earlier sample engagement and the engagement-scoped items around it."""
    eid = eng["id"]
    api.post("/api/engagements/active", {"engagement_id": eid})
    for m in items(api.get("/api/attack-maps"), "maps", "attack_maps"):
        api.delete(f"/api/attack-maps/{m['id']}")
    for p in items(api.get("/api/testplans/plans"), "plans"):
        if p.get("engagement_id") == eid:
            api.delete(f"/api/testplans/plans/{p['id']}")
    for r in items(api.get(f"/api/reporting/reports?engagement_id={eid}"), "reports"):
        api.delete(f"/api/reporting/reports/{r['id']}")
    for f in items(api.get("/api/filters"), "filters"):
        api.delete(f"/api/filters/{f['id']}")
    for r in items(api.get("/api/relationships"), "relationships"):
        api.delete(f"/api/relationships/{r['id']}")
    for p in items(api.get("/api/relationships/paths"), "paths"):
        api.delete(f"/api/relationships/paths/{p['id']}")
    api.delete(f"/api/engagements/{eid}")
    step(f"removed the earlier sample engagement (id {eid})")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load(api):
    ids = {"evidence": {}, "finding": {}, "note": {}, "credential": {}, "host": {}}

    # Client record (global; reused if it already exists)
    client = next((c for c in items(api.get("/api/clients"), "clients") if c.get("name") == C.CLIENT["name"]), None)
    if not client:
        client = api.post("/api/clients", C.CLIENT)
    client_id = client.get("id") or client.get("client", {}).get("id")
    step(f"client '{C.CLIENT['name']}'")

    eng = api.post("/api/engagements", {**C.ENGAGEMENT, "client_id": client_id})
    eid = eng.get("id") or eng.get("engagement", {}).get("id")
    api.post("/api/engagements/active", {"engagement_id": eid})
    step(f"engagement '{C.ENGAGEMENT['name']}' (id {eid}), set active")

    # Tool output: uploaded as evidence, parsed into hosts and ports
    for fname, title, text, tags in C.TOOL_IMPORTS:
        api.post("/api/evidence", {"evidence_type": "tool_output", "title": title, "content": text, "tags": tags},
                 files={"file": FILES / fname})
    step(f"imported {len(C.TOOL_IMPORTS)} tool outputs (Nmap, Nessus, Burp)")

    def refresh_hosts():
        ids["host"] = {h["ip"]: h["id"] for h in items(api.get("/api/hosts"), "hosts")}

    refresh_hosts()
    for h in C.MANUAL_HOSTS:
        if h["ip"] not in ids["host"]:
            created = api.post("/api/hosts", {k: h[k] for k in ("ip", "hostname", "os", "notes")})
            ids["host"][h["ip"]] = created.get("id") or created.get("host", {}).get("id")
        for port, proto, state, service, version in h["ports"]:
            api.post(f"/api/hosts/{ids['host'][h['ip']]}/ports",
                     {"port": port, "protocol": proto, "state": state, "service": service, "version": version})
    step(f"{len(ids['host'])} hosts ({len(C.MANUAL_HOSTS)} added by hand)")

    def host(ip):
        if ip not in ids["host"]:
            raise ApiError(f"host {ip} was not created by the imports; check sample_data/files")
        return ids["host"][ip]

    # Evidence: screenshots and text, linked to hosts
    for ev in C.EVIDENCE:
        fields = {k: ev[k] for k in ("evidence_type", "title", "content", "tags")}
        if ev.get("file"):
            created = api.post("/api/evidence", fields, files={"file": FILES / ev["file"]})
        else:
            created = api.post("/api/evidence", fields)
        ev_id = created.get("id") or created.get("evidence", {}).get("id")
        ids["evidence"][ev["key"]] = ev_id
        for ip in ev.get("hosts", []):
            api.post(f"/api/hosts/{host(ip)}/evidence", {"evidence_id": ev_id})
    step(f"{len(C.EVIDENCE)} evidence items (screenshots, notes, command output)")

    def embed(text):
        """Replace {{shot:<evidence key>}} with the image markdown the note editor inserts on paste."""
        def image(m):
            ev = next(e for e in C.EVIDENCE if e["key"] == m.group(1))
            return f"![{ev['title']}](/api/evidence/{ids['evidence'][ev['key']]}/file)"
        return re.sub(r"\{\{shot:(\w+)\}\}", image, text)

    for ip, status in C.HOST_STATUS.items():
        api.put(f"/api/hosts/{host(ip)}", status)
    for ip, notes in C.HOST_NOTES.items():
        for title, body in notes:
            n = api.post(f"/api/hosts/{host(ip)}/notes", {"title": title, "content": embed(body)})
            ids["note"][f"{ip}:{title}"] = n.get("id")
    for ip, creds in C.HOST_CREDENTIALS.items():
        for cred in creds:
            c = api.post(f"/api/hosts/{host(ip)}/credentials", cred)
            ids["credential"][cred["username"].split("\\")[-1]] = c.get("id")
    step("host indicators, colours, notes and credentials")

    # General section: notes tree, credentials, terminal dumps, findings
    for key, title, parent, body in C.ENGAGEMENT_NOTES:
        payload = {"title": title, "content": embed(body)}
        if parent:
            payload["parent_id"] = ids["note"][parent]
        ids["note"][key] = api.post(f"/api/engagements/{eid}/notes", payload).get("id")
    for cred in C.ENGAGEMENT_CREDENTIALS:
        api.post(f"/api/engagements/{eid}/credentials", cred)
    for dump in C.TERMINAL_DUMPS:
        api.post(f"/api/engagements/{eid}/terminal-dumps", dump)
    for f in C.FINDINGS:
        body = {k: v for k, v in f.items() if k != "key"}
        ids["finding"][f["key"]] = api.post(f"/api/engagements/{eid}/findings", body).get("id")
    step(f"{len(C.ENGAGEMENT_NOTES)} notes, {len(C.ENGAGEMENT_CREDENTIALS)} credentials, "
         f"{len(C.TERMINAL_DUMPS)} terminal dumps, {len(C.FINDINGS)} findings")

    # Relationships and a saved path
    for (st, sk), (tt, tk), rtype, label in C.RELATIONSHIPS:
        api.post("/api/relationships", {
            "source_node_type": st, "source_node_id": ids[st][sk],
            "target_node_type": tt, "target_node_id": ids[tt][tk],
            "type": rtype, "label": label})
    start = f"evidence_{ids['evidence'][C.SAVED_PATH['start']]}"
    end = f"evidence_{ids['evidence'][C.SAVED_PATH['end']]}"
    found = api.post("/api/relationships/path", {"start_id": start, "end_id": end})
    api.post("/api/relationships/paths", {
        "name": C.SAVED_PATH["name"], "description": C.SAVED_PATH["description"],
        "start_id": start, "end_id": end, "path_data": found})
    step(f"{len(C.RELATIONSHIPS)} relationships and a saved attack path")

    # Attack map
    amap = api.post("/api/attack-maps", {"name": C.ATTACK_MAP["name"], "description": C.ATTACK_MAP["description"]})
    map_id = amap.get("id") or amap.get("map", {}).get("id")
    node_ids = {}
    for key, ntype, x, y, label, props in C.ATTACK_MAP["nodes"]:
        props = dict(props)
        node = {"node_type": ntype, "x": x, "y": y, "label": label,
                "width": 80 if ntype == "connector" else 220, "height": 40 if ntype == "connector" else 80}
        ref = props.pop("ref", None)
        if ntype == "host_ref":
            node.update(ref_type="host", ref_id=host(ref))
            props.update(ip=ref, hostname=label)
        elif ntype == "finding_ref":
            node.update(ref_type="finding", ref_id=ids["finding"][ref])
            props["severity"] = next(f["criticality"] for f in C.FINDINGS if f["key"] == ref)
        elif ntype == "evidence_ref":
            node.update(ref_type="evidence", ref_id=ids["evidence"][ref])
            props["title"] = label
        node["properties"] = props
        created = api.post(f"/api/attack-maps/{map_id}/nodes", node)
        node_ids[key] = created.get("id") or created.get("node", {}).get("id")
    for src, dst, label in C.ATTACK_MAP["edges"]:
        api.post(f"/api/attack-maps/{map_id}/edges",
                 {"source_node_id": node_ids[src], "target_node_id": node_ids[dst], "label": label})
    step(f"attack map with {len(node_ids)} nodes")

    for flt in C.SAVED_FILTERS:
        api.post("/api/filters", flt)
    step(f"{len(C.SAVED_FILTERS)} saved host searches")

    # Global libraries: writeups and commands (skipped if already present)
    existing = {w.get("name") for w in items(api.get("/api/reporting/writeups"), "writeups")}
    writeup_ids = {w.get("name"): w.get("id") for w in items(api.get("/api/reporting/writeups"), "writeups")}
    for w in C.WRITEUPS:
        if w["name"] not in existing:
            created = api.post("/api/reporting/writeups", {**w, "tags": C.SAMPLE_TAG})
            writeup_ids[w["name"]] = created.get("id") or created.get("writeup", {}).get("id")
    existing = {c.get("name") for c in items(api.get("/api/commands"), "commands")}
    for cmd in C.COMMANDS:
        if cmd["name"] not in existing:
            api.post("/api/commands", cmd)
    step("writeups and commands added to the shared libraries")

    # ATT&CK layer and test plan
    layer_name = json.loads((FILES / C.ATTACK_LAYER_FILE).read_text())["name"]
    if not any(lay.get("name") == layer_name for lay in items(api.get("/api/testplans/layers"), "layers")):
        api.post("/api/testplans/layers/import", {}, files={"file": FILES / C.ATTACK_LAYER_FILE})
    tp = C.TEST_PLAN
    plan = api.post("/api/testplans/plans", {k: tp[k] for k in ("name", "description", "target_platform", "tags")})
    plan_id = plan.get("id") or plan.get("plan", {}).get("id")
    item_results = {}
    for it in tp["items"]:
        created = api.post(f"/api/testplans/plans/{plan_id}/items",
                           {k: it[k] for k in ("custom_name", "custom_command", "custom_platform")})
        item_results[created.get("id") or created.get("item", {}).get("id")] = it["result"]
    api.post("/api/testplans/executions/start", {"plan_id": plan_id, "host_id": host("10.0.5.10")})
    for ex in items(api.get("/api/testplans/executions"), "executions"):
        result = item_results.get(ex.get("test_plan_item_id") or ex.get("item_id"))
        if ex.get("test_plan_id", plan_id) != plan_id or not result:
            continue
        result = dict(result)
        evidence_key = result.pop("evidence", None)
        api.put(f"/api/testplans/executions/{ex['id']}", result)
        if evidence_key:
            api.post(f"/api/testplans/executions/{ex['id']}/link-evidence",
                     {"evidence_id": ids["evidence"][evidence_key]})
    step("ATT&CK layer, test plan and recorded executions against DC01")

    # Report
    structure = []
    for n, entry in enumerate(C.REPORT):
        kind = entry[0]
        item = {"id": f"sample-{n}", "position": n, "customizations": {}}
        if kind == "tool":
            item.update(type="format_tool", source_id=entry[1], writeup_type="format_tool",
                        format_tool_id=entry[1], title=TOOL_TITLES[entry[1]], toolData=entry[2])
        elif kind == "table":
            item.update(type="format_tool", source_id="table", writeup_type="format_tool",
                        format_tool_id="table", title=TOOL_TITLES["table"],
                        tableData={"headers": entry[1], "rows": entry[2]})
        elif kind == "attackmap":
            item.update(type="format_tool", source_id="attackmap", writeup_type="format_tool",
                        format_tool_id="attackmap", title=TOOL_TITLES["attackmap"],
                        toolData={"mapId": map_id, "mapName": C.ATTACK_MAP["name"]})
        elif kind == "finding":
            item.update(type="engagement_finding", source_id=ids["finding"][entry[1]])
        elif kind == "writeup":
            wid = writeup_ids.get(entry[1])
            if wid is None:
                continue
            wtype = next((w["writeup_type"] for w in C.WRITEUPS if w["name"] == entry[1]), "finding")
            item.update(type="writeup", source_id=wid)
            if wtype == "narrative":
                item["writeup_type"] = "narrative"
        structure.append(item)
    api.post("/api/reporting/reports", {"name": C.REPORT_NAME, "structure": structure, "engagement_id": eid})
    step(f"report '{C.REPORT_NAME}' with {len(structure)} items")
    return eid


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default="http://localhost:5001", help="PTVault address (default %(default)s)")
    ap.add_argument("--email", required=True, help="admin or tester account (email or username)")
    ap.add_argument("--replace", action="store_true", help="delete an earlier sample engagement first")
    args = ap.parse_args()

    password = os.environ.get("PTVAULT_PASSWORD") or getpass.getpass(f"Password for {args.email}: ")
    api = Client(args.url)
    try:
        api.login(args.email, password)
        existing = find_sample(api)
        if existing:
            if not args.replace:
                sys.exit(f"A sample engagement ({C.SHORT_NAME}, id {existing['id']}) already exists. "
                         "Rerun with --replace to delete and reload it.")
            remove_sample(api, existing)
        print(f"Loading the sample engagement into {args.url}")
        eid = load(api)
    except ApiError as e:
        sys.exit(f"Failed: {e}")
    print(f"\nDone. Open {args.url}, pick '{C.ENGAGEMENT['name']}' (id {eid}) and start with the "
          "note 'Start here' under General -> Notes.")


if __name__ == "__main__":
    main()

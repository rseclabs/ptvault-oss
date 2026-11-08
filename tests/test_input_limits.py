"""Input limits (retest L-19).

?limit=-1 removed the result cap (SQLite treats LIMIT -1 as no limit) and a
non-number was a 500; the 250 MB upload limit was the only limit on JSON
bodies; an uploaded XML file was parsed into a full tree twice (once only to
read its root tag).
"""

import pytest
from flask import Flask, jsonify, request

from tests.conftest import ENGAGEMENT_A


@pytest.fixture
def searchable(live_app):
    conn = live_app.db()
    for i in range(60):
        conn.execute("INSERT INTO evidence (engagement_id, evidence_type, title, content, tags) "
                     "VALUES (?, 'note', ?, 'needle', 'common')", (ENGAGEMENT_A, f'n{i}'))
    conn.commit()
    conn.close()
    return live_app.client_for('viewer', active_engagement=ENGAGEMENT_A)


def _count(resp):
    body = resp.get_json()
    for key in ('results', 'evidence', 'items'):
        if isinstance(body, dict) and key in body:
            return len(body[key])
    return len(body)


@pytest.mark.parametrize('url', ['/api/evidence/search?q=needle', '/api/evidence/filter?tags=common'])
@pytest.mark.parametrize('limit, expected', [('-1', 1), ('0', 1), ('5', 5), ('100000', 60), ('abc', 50)])
def test_result_limits_are_clamped(searchable, url, limit, expected):
    resp = searchable.get(f'{url}&limit={limit}')
    assert resp.status_code == 200, resp.get_json()
    assert _count(resp) == expected


@pytest.mark.parametrize('offset', ['-5', 'x'])
def test_a_bad_offset_is_not_an_error(searchable, offset):
    assert searchable.get(f'/api/evidence/filter?tags=common&offset={offset}').status_code == 200


@pytest.mark.parametrize('limit', ['-1', 'abc', '1000'])
def test_tag_suggestions_are_clamped(searchable, limit):
    resp = searchable.get(f'/api/tags/autocomplete?q=c&limit={limit}')
    assert resp.status_code == 200


def test_bounded_int():
    from utils.helpers import bounded_int
    assert bounded_int('-1', 50, 1, 500) == 1
    assert bounded_int('9999', 50, 1, 500) == 500
    assert bounded_int(None, 50, 1, 500) == 50
    assert bounded_int('x', 50, 1, 500) == 50
    assert bounded_int('7', 50, 1, 500) == 7


# ------------------------------------------------------------------ body size

@pytest.fixture
def body_app():
    from config import Config
    from utils.request_limits import limit_request_body
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE
    app.before_request(limit_request_body)

    @app.route('/json', methods=['POST'])
    def json_body():
        return jsonify({'size': len(request.get_json()['x'])})

    @app.route('/upload', methods=['POST'])
    def upload():
        return jsonify({'size': len(request.files['file'].read())})
    return app.test_client()


def test_json_bodies_have_a_smaller_limit(body_app):
    from config import Config
    big = 'a' * (Config.MAX_JSON_SIZE + 1)
    assert body_app.post('/json', json={'x': big}).status_code == 413
    assert body_app.post('/json', json={'x': 'a' * 1000}).get_json() == {'size': 1000}


def test_file_uploads_keep_the_upload_limit(body_app):
    import io
    from config import Config
    data = b'a' * (Config.MAX_JSON_SIZE + 1)
    resp = body_app.post('/upload', data={'file': (io.BytesIO(data), 'big.txt')}, content_type='multipart/form-data')
    assert resp.status_code == 200 and resp.get_json() == {'size': len(data)}


# ------------------------------------------------------------------ XML

def test_tool_detection_reads_only_the_root_element():
    from routes.evidence import detect_tool_type
    # Only the opening root tag is read: the rest of the file is never parsed here
    assert detect_tool_type(b'<?xml version="1.0"?><nmaprun scanner="nmap"><host>' + b'<x/>' * 10) == 'nmap'
    assert detect_tool_type(b'<NessusClientData_v2><Report') == 'nessus'
    assert detect_tool_type(b'<issues burpVersion="1">') == 'burp'
    assert detect_tool_type(b'<other/>') is None
    assert detect_tool_type(b'not xml at all') is None
    # Entities are still refused (defusedxml)
    assert detect_tool_type(b'<!DOCTYPE x [<!ENTITY e "boom">]><nmaprun>&e;</nmaprun>') is None


# ------------------------------------------------------------------ JSON files (retest 2: M-18)

@pytest.mark.parametrize('url, name', [('/api/engagements/import', 'e.json'), ('/api/testplans/layers/import', 'l.json')])
def test_json_files_are_capped_before_they_are_parsed(live_app, url, name):
    import io
    from config import Config
    client = live_app.client_for('owner', active_engagement=ENGAGEMENT_A)
    big = b'[' + b'{},' * ((Config.MAX_JSON_SIZE + 1_000_000) // 3) + b'{}]'
    resp = client.post(url, data={'file': (io.BytesIO(big), name)}, content_type='multipart/form-data')
    assert resp.status_code == 413, resp.get_json()


@pytest.mark.parametrize('url, name', [('/api/engagements/import', 'e.json'), ('/api/testplans/layers/import', 'l.json')])
def test_deeply_nested_json_files_are_a_400(live_app, url, name):
    import io
    client = live_app.client_for('owner', active_engagement=ENGAGEMENT_A)
    deep = b'[' * 100_000 + b']' * 100_000
    resp = client.post(url, data={'file': (io.BytesIO(deep), name)}, content_type='multipart/form-data')
    assert resp.status_code == 400

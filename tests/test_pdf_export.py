"""H-7: PDF export cannot read local files or reach the network.

WeasyPrint gets a fetcher that allows only data: URLs, every interpolated
cover-page field is escaped, and structural report fields are allow-listed so
they cannot inject markup or CSS.
"""

import http.server
import threading

import pytest

from routes.reporting import generate_html_export
from utils import pdf_generator
from utils.pdf_generator import HAS_WEASYPRINT, _generate_cover_page

needs_weasyprint = pytest.mark.skipif(not HAS_WEASYPRINT, reason='WeasyPrint not installed')
ATTACH = '<a rel="attachment" href="file://{path}">x</a>'


@pytest.fixture
def secret_file(tmp_path):
    path = tmp_path / 'encryption.key'
    path.write_text('TOP-SECRET-KEY-MATERIAL')
    return path


def _has_attachment(pdf_bytes):
    return b'EmbeddedFile' in pdf_bytes


# ------------------------------------------------------------- cover page

def test_cover_page_escapes_every_field(secret_file):
    payload = ATTACH.format(path=secret_file)
    cover = _generate_cover_page(
        {'name': payload, 'client_name': payload, 'start_date': payload, 'end_date': payload}, payload)
    assert '<a ' not in cover and '&lt;a rel=&quot;attachment&quot;' in cover


@needs_weasyprint
def test_report_name_cannot_attach_a_local_file(secret_file):
    pdf = pdf_generator.generate_pdf_with_cover(
        '<html><body><p>body</p></body></html>', engagement_data={'name': 'E'},
        report_name=ATTACH.format(path=secret_file))
    assert not _has_attachment(pdf)


# ------------------------------------------------------------- fetcher

@needs_weasyprint
def test_fetcher_blocks_file_urls_even_in_trusted_html(secret_file):
    # Defence in depth: even markup that reaches WeasyPrint unescaped cannot load files.
    html = f'<html><body>{ATTACH.format(path=secret_file)}<img src="file://{secret_file}"></body></html>'
    assert not _has_attachment(pdf_generator.generate_pdf_from_html(html))


@needs_weasyprint
def test_fetcher_makes_no_network_requests():
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        html = (f'<html><head><link rel="stylesheet" href="http://127.0.0.1:{port}/s.css"></head>'
                f'<body><img src="http://127.0.0.1:{port}/i.png"></body></html>')
        pdf_generator.generate_pdf_from_html(html)
    finally:
        server.shutdown()
    assert hits == []


@needs_weasyprint
def test_data_urls_still_render():
    pixel = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
             '+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
    pdf = pdf_generator.generate_pdf_from_html(f'<html><body><img src="{pixel}"></body></html>')
    assert pdf.startswith(b'%PDF')


# ------------------------------------------------------------- structural fields

def _export(items):
    return generate_html_export({'name': 'R'}, items)


def _format_tool(tool_id, data):
    return {'type': 'format_tool', 'format_tool_id': tool_id, 'toolData': data}


INJECT = '"><a rel="attachment" href="file:///etc/hostname">x</a><i class="'


@pytest.mark.parametrize('item', [
    _format_tool('sectionheader', {'level': INJECT, 'text': 'T'}),
    _format_tool('imageplaceholder', {'width': 'url(file:///etc/hostname)', 'caption': 'c'}),
    _format_tool('imageplaceholder', {'width': INJECT, 'caption': 'c'}),
    _format_tool('riskmatrix', {'size': INJECT}),
    _format_tool('cvsscard', {'score': INJECT, 'vector': 'v'}),
    {'type': 'writeup', 'writeup_type': 'finding', 'title': 't', 'criticality': INJECT, 'cvss_score': INJECT},
    {'type': 'writeup', 'writeup_type': 'finding', 'title': 't', 'heading_level': 'h3><a rel="attachment"'},
    {'type': 'writeup', 'writeup_type': 'narrative', 'title': 't', 'heading_level': 'script'},
])
def test_structural_fields_cannot_inject_markup(item):
    out = _export([item])
    assert 'rel="attachment"' not in out
    assert 'url(file' not in out
    assert '<script' not in out


def test_valid_structural_values_are_kept():
    out = _export([
        _format_tool('sectionheader', {'level': 3, 'text': 'T'}),
        _format_tool('imageplaceholder', {'width': '50%', 'caption': 'c'}),
        _format_tool('riskmatrix', {'size': 5}),
        _format_tool('cvsscard', {'score': 9.8, 'vector': 'v'}),
        {'type': 'writeup', 'writeup_type': 'finding', 'title': 't', 'criticality': 'high',
         'cvss_score': 7.5, 'heading_level': 'h2'},
    ])
    for expected in ('<h3 class="preview-sectionheader">', 'width: 50%', 'size-5', '9.8',
                     'criticality-high', 'CVSS: 7.5', '<h2>t</h2>'):
        assert expected in out, expected

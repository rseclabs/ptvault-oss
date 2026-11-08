"""Server-side SVG generator for attack maps.

Renders an attack map as a standalone SVG string for embedding
in reports (HTML, Markdown, DOCX).
"""

import json
import math
from xml.sax.saxutils import escape as xml_escape


NODE_COLORS = {
    'recon': '#4a7eb5',
    'tactic': '#4a9e6b',
    'exploit': '#c45c5c',
    'connector': '#c98544',
    'evidence_ref': '#4a9e94',
    'finding_ref': '#9278c4',
    'host_ref': '#4a9eb5',
}

NODE_LABELS = {
    'recon': 'Recon',
    'tactic': 'Tactic',
    'exploit': 'Exploit',
    'connector': 'Connector',
    'evidence_ref': 'Evidence',
    'finding_ref': 'Finding',
    'host_ref': 'Host',
}


def generate_attack_map_svg(attack_map):
    """Generate an SVG string from an attack map dict (with nodes and edges).

    Args:
        attack_map: Dict with 'nodes' and 'edges' lists, plus 'name'.

    Returns:
        SVG string.
    """
    nodes = attack_map.get('nodes', [])
    edges = attack_map.get('edges', [])
    name = attack_map.get('name', 'Attack Map')

    if not nodes:
        return _empty_svg(name)

    # Build node lookup
    node_map = {n['id']: n for n in nodes}

    # Calculate bounding box
    min_x = min(n.get('x', 0) for n in nodes) - 40
    min_y = min(n.get('y', 0) for n in nodes) - 60
    max_x = max(n.get('x', 0) + n.get('width', 220) for n in nodes) + 40
    max_y = max(n.get('y', 0) + _node_height(n) for n in nodes) + 40
    width = max(max_x - min_x, 200)
    height = max(max_y - min_y, 150)

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'viewBox="{min_x} {min_y} {width} {height}" '
                 f'width="{width}" height="{height}" '
                 f'style="background:#0e1114;font-family:sans-serif;">')

    # Arrow marker
    parts.append('<defs>')
    parts.append('<marker id="ah" viewBox="0 0 10 7" refX="10" refY="3.5" '
                 'markerWidth="10" markerHeight="7" orient="auto">')
    parts.append('<polygon points="0 0,10 3.5,0 7" fill="#a1a8b1"/>')
    parts.append('</marker>')
    parts.append('</defs>')

    # Title
    parts.append(f'<text x="{min_x + 10}" y="{min_y + 20}" fill="#a1a8b1" '
                 f'font-size="14" font-weight="600">{xml_escape(name)}</text>')

    # Edges
    for edge in edges:
        src = node_map.get(edge.get('source_node_id'))
        tgt = node_map.get(edge.get('target_node_id'))
        if not src or not tgt:
            continue

        sw, sh = _node_dims(src)
        tw, th = _node_dims(tgt)
        sx = src.get('x', 0) + sw / 2
        sy = src.get('y', 0) + sh / 2
        tx = tgt.get('x', 0) + tw / 2
        ty = tgt.get('y', 0) + th / 2

        angle = math.atan2(ty - sy, tx - sx)
        margin = 4
        x1 = sx + math.cos(angle) * (sw / 2 + margin)
        y1 = sy + math.sin(angle) * (sh / 2 + margin)
        x2 = tx - math.cos(angle) * (tw / 2 + margin)
        y2 = ty - math.sin(angle) * (th / 2 + margin)

        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="#a1a8b1" stroke-width="2" marker-end="url(#ah)"/>')

        label = edge.get('label', '')
        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2 - 8
            parts.append(f'<text x="{mx:.1f}" y="{my:.1f}" fill="#a1a8b1" '
                         f'font-size="11" text-anchor="middle">{xml_escape(label)}</text>')

    # Nodes
    for node in nodes:
        parts.append(_render_node_svg(node))

    parts.append('</svg>')
    return '\n'.join(parts)


def _render_node_svg(node):
    """Render a single node as SVG elements."""
    node_type = node.get('node_type', 'action')
    color = NODE_COLORS.get(node_type, '#6b7280')
    x = node.get('x', 0)
    y = node.get('y', 0)
    is_logic = node_type in ('connector',)
    label = node.get('label', '') or NODE_LABELS.get(node_type, '')
    type_label = NODE_LABELS.get(node_type, node_type)
    props = _properties(node)

    parts = []

    if is_logic:
        conn_label = label or 'Connector'
        w = max(80, len(conn_label) * 9 + 30)
        h = 40
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                     f'rx="20" ry="20" fill="{color}"/>')
        parts.append(f'<text x="{x + w/2}" y="{y + h/2 + 1}" text-anchor="middle" '
                     f'dominant-baseline="middle" fill="#fff" font-size="14" '
                     f'font-weight="700">{xml_escape(conn_label)}</text>')
    else:
        w = node.get('width', 220)
        header_h = 24
        lines = []
        if label:
            lines.append(label)
        if props.get('ttp'):
            lines.append(f"TTP: {props['ttp']}")
        if props.get('service'):
            lines.append(f"Service: {props['service']}")
        if props.get('cve'):
            lines.append(f"CVE: {props['cve']}")
        if props.get('hostname'):
            lines.append(props['hostname'])
        if props.get('description'):
            lines.append(props['description'][:80])

        content_h = max(30, len(lines) * 16 + 10)
        h = header_h + content_h

        # Background
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                     f'rx="8" ry="8" fill="#1b1f24" stroke="{color}" stroke-width="1.5"/>')
        # Header
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{header_h}" '
                     f'rx="8" ry="8" fill="{color}"/>')
        parts.append(f'<rect x="{x}" y="{y + header_h - 8}" width="{w}" height="8" fill="{color}"/>')
        # Type label
        parts.append(f'<text x="{x + 8}" y="{y + header_h/2 + 1}" dominant-baseline="middle" '
                     f'fill="#fff" font-size="11" font-weight="600">{xml_escape(type_label)}</text>')
        # Content
        for idx, line in enumerate(lines):
            line_y = y + header_h + 10 + idx * 16 + 12
            fill = '#eef0f3' if idx == 0 else '#a1a8b1'
            weight = '600' if idx == 0 else '400'
            text = xml_escape(line[:35])
            parts.append(f'<text x="{x + 8}" y="{line_y}" fill="{fill}" '
                         f'font-size="12" font-weight="{weight}">{text}</text>')

    return '\n'.join(parts)


def _properties(node):
    """A node's properties as a dict; anything else stored (null, a list, bad JSON) is empty."""
    props = node.get('properties')
    if isinstance(props, str):
        try:
            props = json.loads(props)
        except (json.JSONDecodeError, TypeError):
            props = None
    return props if isinstance(props, dict) else {}


def _node_height(node):
    """Calculate approximate rendered height."""
    if node.get('node_type') in ('connector',):
        return 40
    props = _properties(node)
    lines = 1
    if props.get('description'):
        lines += 1
    if props.get('technique_id'):
        lines += 1
    return 24 + max(30, lines * 16 + 10)


def _node_dims(node):
    """Get (width, height) for a node."""
    if node.get('node_type') in ('connector',):
        return 80, 40
    return node.get('width', 220), _node_height(node)


def _empty_svg(name):
    """Return a placeholder SVG for empty maps."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 100" '
            f'width="400" height="100" style="background:#0e1114;font-family:sans-serif;">'
            f'<text x="200" y="50" text-anchor="middle" fill="#a1a8b1" font-size="14">'
            f'{xml_escape(name)} - No nodes</text></svg>')

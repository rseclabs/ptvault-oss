"""Shared utility helpers for PTVault."""

# Values the UI renders into markup (H-10): anything else is rejected at the API
# or skipped on import, so a stored field cannot carry markup or script.
PORT_PROTOCOLS = frozenset(['tcp', 'udp', 'sctp', 'ip', 'icmp'])
PORT_STATES = frozenset(['open', 'closed', 'filtered', 'unfiltered', 'open|filtered', 'closed|filtered',
                         'unknown'])
HOST_COLORS = frozenset(['white', 'yellow', 'green', 'blue', 'red', 'purple', 'orange', 'teal', 'cyan', 'brown'])


def parse_port_number(value):
    """Return value as a port number (0-65535), or raise ValueError."""
    if isinstance(value, bool):
        raise ValueError('port must be an integer')
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            raise ValueError('port must be an integer')
    if isinstance(value, float) and not value.is_integer():
        raise ValueError('port must be an integer')
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ValueError('port must be an integer')
    if not 0 <= port <= 65535:
        raise ValueError('port must be between 0 and 65535')
    return port


def parse_port_choice(value, allowed, field):
    """Return value lower-cased if it is in allowed, or raise ValueError."""
    normalised = value.strip().lower() if isinstance(value, str) else None
    if normalised not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return normalised


def parse_port_fields(port, protocol='tcp', state='open'):
    """Validate a port row's rendered fields; return (port, protocol, state) or raise ValueError."""
    return (parse_port_number(port),
            parse_port_choice(protocol, PORT_PROTOCOLS, 'protocol'),
            parse_port_choice(state, PORT_STATES, 'state'))


def normalize_tags(tags_input):
    """
    Normalize tags from various input formats to a clean comma-separated string.

    Handles:
    - Comma-separated strings: "tag1, tag2, tag3"
    - Lists: ["tag1", "tag2"]
    - None/empty: returns empty string

    Args:
        tags_input: Tags as string, list, or None

    Returns:
        str: Cleaned, lowercase, comma-separated tags
    """
    if not tags_input:
        return ''

    if isinstance(tags_input, list):
        tags = tags_input
    elif isinstance(tags_input, str):
        tags = [t.strip() for t in tags_input.split(',')]
    else:
        return ''

    # Clean, deduplicate, sort
    cleaned = sorted(set(t.strip().lower() for t in tags if t.strip()))
    return ','.join(cleaned)

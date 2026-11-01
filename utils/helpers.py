"""Shared utility helpers for PTVault."""


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

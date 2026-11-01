"""
Navigator Layer Parser for PTVault.
Parses MITRE ATT&CK Navigator layer JSON files and extracts technique data.
"""

import json


def parse_navigator_layer(layer_json):
    """
    Parse a Navigator layer JSON and extract technique information.

    Args:
        layer_json: Either a JSON string or dict containing layer data

    Returns:
        dict: Parsed layer data with normalized technique info
    """
    if isinstance(layer_json, str):
        layer_data = json.loads(layer_json)
    else:
        layer_data = layer_json

    # Extract basic layer info
    result = {
        "name": layer_data.get("name", "Unnamed Layer"),
        "description": layer_data.get("description", ""),
        "domain": layer_data.get("domain", "enterprise-attack"),
        "version": layer_data.get("version", ""),
        "techniques": [],
        "filters": extract_layer_filters(layer_data),
        "gradient": layer_data.get("gradient", {}),
        "legendItems": layer_data.get("legendItems", [])
    }

    # Parse techniques
    for tech in layer_data.get("techniques", []):
        technique = parse_technique(tech)
        if technique:
            result["techniques"].append(technique)

    return result


def parse_technique(tech_data):
    """
    Parse a single technique entry from the layer.

    Args:
        tech_data: Technique dict from layer JSON

    Returns:
        dict: Normalized technique data
    """
    technique_id = tech_data.get("techniqueID", "")
    if not technique_id:
        return None

    return {
        "technique_id": technique_id,
        "tactic": tech_data.get("tactic", ""),
        "score": tech_data.get("score", 0) or 0,
        "color": tech_data.get("color", ""),
        "comment": tech_data.get("comment", ""),
        "enabled": tech_data.get("enabled", True),
        "metadata": tech_data.get("metadata", []),
        "links": tech_data.get("links", []),
        "showSubtechniques": tech_data.get("showSubtechniques", False)
    }


def extract_layer_filters(layer_data):
    """
    Extract available filter options from the layer.

    Args:
        layer_data: Full layer dict

    Returns:
        dict: Available filters (colors, score range, tactics)
    """
    techniques = layer_data.get("techniques", [])

    colors = set()
    scores = []
    tactics = set()

    for tech in techniques:
        color = tech.get("color", "")
        if color:
            colors.add(color)

        score = tech.get("score", 0)
        if score is not None:
            scores.append(score)

        tactic = tech.get("tactic", "")
        if tactic:
            tactics.add(tactic)

    return {
        "colors": sorted(list(colors)),
        "score_min": min(scores) if scores else 0,
        "score_max": max(scores) if scores else 0,
        "tactics": sorted(list(tactics))
    }


def get_technique_summary(layer_data):
    """
    Get a summary of techniques in the layer grouped by various attributes.

    Args:
        layer_data: Parsed layer data

    Returns:
        dict: Summary statistics
    """
    techniques = layer_data.get("techniques", [])

    by_tactic = {}
    by_color = {}
    by_score_range = {
        "0": 0,
        "1-25": 0,
        "26-50": 0,
        "51-75": 0,
        "76-100": 0
    }

    for tech in techniques:
        # By tactic
        tactic = tech.get("tactic", "unknown")
        by_tactic[tactic] = by_tactic.get(tactic, 0) + 1

        # By color
        color = tech.get("color", "none")
        if not color:
            color = "none"
        by_color[color] = by_color.get(color, 0) + 1

        # By score range
        score = tech.get("score", 0) or 0
        if score == 0:
            by_score_range["0"] += 1
        elif score <= 25:
            by_score_range["1-25"] += 1
        elif score <= 50:
            by_score_range["26-50"] += 1
        elif score <= 75:
            by_score_range["51-75"] += 1
        else:
            by_score_range["76-100"] += 1

    return {
        "total": len(techniques),
        "by_tactic": by_tactic,
        "by_color": by_color,
        "by_score_range": by_score_range
    }


def filter_techniques(techniques, min_score=0, max_score=100, colors=None, tactics=None, enabled_only=True):
    """
    Filter techniques based on criteria.

    Args:
        techniques: List of technique dicts
        min_score: Minimum score to include
        max_score: Maximum score to include
        colors: List of colors to include (None = all)
        tactics: List of tactics to include (None = all)
        enabled_only: Only include enabled techniques

    Returns:
        list: Filtered techniques
    """
    filtered = []

    for tech in techniques:
        # Check enabled
        if enabled_only and not tech.get("enabled", True):
            continue

        # Check score
        score = tech.get("score", 0) or 0
        if score < min_score or score > max_score:
            continue

        # Check color
        if colors:
            tech_color = tech.get("color", "")
            if tech_color not in colors:
                continue

        # Check tactic
        if tactics:
            tech_tactic = tech.get("tactic", "")
            if tech_tactic not in tactics:
                continue

        filtered.append(tech)

    return filtered


def get_unique_technique_ids(techniques):
    """
    Get unique technique IDs from a list of techniques.
    Handles sub-techniques by optionally grouping with parent.

    Args:
        techniques: List of technique dicts

    Returns:
        list: Unique technique IDs
    """
    ids = set()
    for tech in techniques:
        technique_id = tech.get("technique_id", "")
        if technique_id:
            ids.add(technique_id)
    return sorted(list(ids))

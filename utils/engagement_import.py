"""Validation for engagement import files (H-17).

An export file is user-supplied JSON, so every value that a create route would
check is checked here too, with the same allow-lists, and the whole file is
rejected (before anything is written) if one value fails. Records are
normalised in place: defaults filled in the way the create routes fill them,
flags as 0/1, metadata as a JSON object string.

Host ports are the exception: invalid port rows are skipped on import (H-10),
which import_engagement_data does itself.
"""

import json

from utils.helpers import (
    ENGAGEMENT_CREDENTIAL_TYPES,
    ENGAGEMENT_STATUSES,
    EVIDENCE_TYPES,
    FINDING_CRITICALITIES,
    PASSWORD_TYPES,
    normalize_tags,
    parse_cvss_score,
    validate_date,
    validate_email,
)

HOST_FLAGS = ('rooted', 'shell', 'interested', 'not_interested', 'out_of_scope', 'flagged', 'reviewed')

# Free-text columns per collection: rendered escaped, but they must be text.
TEXT_FIELDS = {
    'engagement': ('client_name', 'short_name', 'description', 'contact_name', 'contact_phone'),
    'hosts': ('hostname', 'os', 'notes'),
    'evidence': ('title', 'content'),
    'host_notes': ('content',),
    'host_ports': ('service', 'version'),
    'host_credentials': ('username', 'password', 'hash_type', 'service', 'notes'),
    'evidence_hosts': ('source',),
    'engagement_notes': ('content',),
    'engagement_credentials': ('username', 'password_or_hash', 'description'),
    'terminal_dumps': ('title', 'content', 'session_datetime'),
    'engagement_findings': ('ip_address', 'hostname', 'finding_content', 'remediation_content'),
}
# Old ids that link records inside the file; they become dictionary keys.
REFERENCE_FIELDS = {
    'hosts': ('id',),
    'evidence': ('id',),
    'host_notes': ('host_id',),
    'host_ports': ('host_id',),
    'host_credentials': ('host_id',),
    'evidence_hosts': ('evidence_id', 'host_id'),
}


class ImportValidationError(ValueError):
    """An import file value failed validation; the message names the record."""


def _fail(where, message):
    raise ImportValidationError(f'{where}: {message}')


def _choice(record, field, allowed, default, where):
    value = record.get(field)
    if value is None or value == '':
        value = default
    if value not in allowed:
        _fail(where, f"{field} must be one of: {', '.join(allowed)}")
    record[field] = value


def _flag(record, field, where):
    value = record.get(field, 0)
    if value is None:
        value = 0
    if value not in (0, 1) or isinstance(value, float):      # True/False compare equal to 1/0
        _fail(where, f'{field} must be 0, 1, true or false')
    record[field] = int(value)


def _metadata(value, where):
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            _fail(where, 'metadata must be a JSON object')
    if not isinstance(value, dict):
        _fail(where, 'metadata must be a JSON object')
    return json.dumps(value)


def _engagement(eng):
    where = 'engagement'
    name = eng.get('name', 'Imported Engagement')
    if not isinstance(name, str) or not name.strip():
        _fail(where, 'name must be non-empty text')
    _choice(eng, 'status', ENGAGEMENT_STATUSES, 'active', where)
    for field in ('start_date', 'end_date'):
        if not validate_date(eng.get(field)):
            _fail(where, f'{field} must be a date (YYYY-MM-DD)')
        eng[field] = eng.get(field) or None
    if not validate_email(eng.get('contact_email')):
        _fail(where, 'contact_email is not a valid email address')
    eng['contact_email'] = eng.get('contact_email') or None
    tags = eng.get('tags')
    if tags is not None and not isinstance(tags, (str, list)):
        _fail(where, 'tags must be text or a list')
    if isinstance(tags, list) and not all(isinstance(t, str) for t in tags):
        _fail(where, 'tags must be text')
    eng['tags'] = normalize_tags(tags)


def _record(name, index, record):
    where = f'{name}[{index}]'
    for field in TEXT_FIELDS.get(name, ()):
        if record.get(field) is not None and not isinstance(record[field], str):
            _fail(where, f'{field} must be text')
    for field in REFERENCE_FIELDS.get(name, ()):
        value = record.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, str))):
            _fail(where, f'{field} must be an id')

    if name == 'hosts':
        if not isinstance(record.get('ip'), str) or not record['ip'].strip():
            _fail(where, 'ip is required')
        if 'shell' not in record and 'has_shell' in record:
            record['shell'] = record['has_shell']
        for field in HOST_FLAGS:
            _flag(record, field, where)
        record['has_shell'] = record['shell']
    elif name == 'evidence':
        if record.get('evidence_type') not in EVIDENCE_TYPES:
            _fail(where, f"evidence_type must be one of: {', '.join(EVIDENCE_TYPES)}")
        tags = record.get('tags') or []
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            _fail(where, 'tags must be a list of text')
        record['tags'] = tags
        record['metadata'] = _metadata(record.get('metadata'), where)
    elif name == 'host_credentials':
        _choice(record, 'password_type', tuple(sorted(PASSWORD_TYPES)), 'cleartext', where)
    elif name == 'engagement_credentials':
        _choice(record, 'credential_type', ENGAGEMENT_CREDENTIAL_TYPES, 'clear_text', where)
    elif name == 'engagement_findings':
        if not isinstance(record.get('title'), str) or not record['title'].strip():
            _fail(where, 'title is required')
        _choice(record, 'criticality', FINDING_CRITICALITIES, 'medium', where)
        try:
            record['cvss_score'] = parse_cvss_score(record.get('cvss_score'))
        except ValueError as e:
            _fail(where, str(e))
        record.setdefault('include_in_report', 1)
        _flag(record, 'include_in_report', where)


def validate_import(data, collections):
    """Check and normalise an export file in place; raise ImportValidationError.

    data must already have the shape _import_shape_error checks (an engagement
    object and lists of objects).
    """
    _engagement(data['engagement'])
    for name in collections:
        for index, record in enumerate(data.get(name, [])):
            _record(name, index, record)

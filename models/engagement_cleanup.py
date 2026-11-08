"""Deleting an engagement or evidence completely (M-13).

Foreign keys are not enforced in PTVault's databases, so nothing cascades: every
table that holds an engagement's data is listed here and cleared explicitly.
The caller commits, so a delete is one transaction. purge_orphans() removes what
the earlier, incomplete delete left behind (used by migration 034).

audit_log is deliberately kept: it is the record that the delete happened.
"""

import logging
import os
import shutil

logger = logging.getLogger(__name__)


def _ids(cursor, sql, params=()):
    return [row[0] for row in cursor.execute(sql, params).fetchall()]


def _in(ids):
    return ','.join('?' * len(ids))


def delete_evidence_rows(cursor, evidence_ids):
    """Delete evidence and every row that points at it.

    Links (tags, hosts, relationships, attack paths) are deleted; host ports and
    test executions keep their own data and only drop the reference.
    """
    evidence_ids = list(evidence_ids)
    if not evidence_ids:
        return
    marks = _in(evidence_ids)
    cursor.execute(f'DELETE FROM evidence_tags WHERE evidence_id IN ({marks})', evidence_ids)
    cursor.execute(f'DELETE FROM evidence_hosts WHERE evidence_id IN ({marks})', evidence_ids)
    cursor.execute(f"DELETE FROM node_relationships WHERE (source_node_type = 'evidence' AND source_node_id IN ({marks}))"
                   f" OR (target_node_type = 'evidence' AND target_node_id IN ({marks}))", evidence_ids * 2)
    cursor.execute(f'DELETE FROM attack_paths WHERE start_evidence_id IN ({marks}) OR end_evidence_id IN ({marks})',
                   evidence_ids * 2)
    cursor.execute(f'UPDATE host_ports SET evidence_id = NULL WHERE evidence_id IN ({marks})', evidence_ids)
    cursor.execute(f'UPDATE test_executions SET evidence_id = NULL WHERE evidence_id IN ({marks})', evidence_ids)
    cursor.execute(f'DELETE FROM evidence WHERE id IN ({marks})', evidence_ids)


def _delete_hosts(cursor, host_ids):
    if not host_ids:
        return
    marks = _in(host_ids)
    for table in ('host_notes', 'host_ports', 'host_credentials', 'evidence_hosts'):
        cursor.execute(f'DELETE FROM {table} WHERE host_id IN ({marks})', host_ids)
    cursor.execute(f'DELETE FROM hosts WHERE id IN ({marks})', host_ids)


def _delete_reports(cursor, report_ids):
    if report_ids:
        marks = _in(report_ids)
        cursor.execute(f'DELETE FROM report_sections WHERE report_id IN ({marks})', report_ids)
        cursor.execute(f'DELETE FROM reports WHERE id IN ({marks})', report_ids)


def _delete_maps(cursor, map_ids):
    if map_ids:
        marks = _in(map_ids)
        cursor.execute(f'DELETE FROM attack_map_edges WHERE map_id IN ({marks})', map_ids)
        cursor.execute(f'DELETE FROM attack_map_nodes WHERE map_id IN ({marks})', map_ids)
        cursor.execute(f'DELETE FROM attack_maps WHERE id IN ({marks})', map_ids)


def _delete_plans(cursor, plan_ids):
    if plan_ids:
        marks = _in(plan_ids)
        cursor.execute(f'DELETE FROM test_executions WHERE test_plan_id IN ({marks})', plan_ids)
        cursor.execute(f'DELETE FROM test_plan_items WHERE test_plan_id IN ({marks})', plan_ids)
        cursor.execute(f'DELETE FROM test_plans WHERE id IN ({marks})', plan_ids)


# Tables with an engagement_id and no children of their own
_DIRECT = ('engagement_notes', 'engagement_credentials', 'terminal_dumps', 'engagement_findings',
           'engagement_members', 'saved_filters', 'test_executions', 'node_relationships', 'attack_paths')


def delete_engagement(cursor, engagement_id):
    """Delete an engagement and everything that belongs to it (not committed)."""
    e = (engagement_id,)
    delete_evidence_rows(cursor, _ids(cursor, 'SELECT id FROM evidence WHERE engagement_id = ?', e))
    _delete_hosts(cursor, _ids(cursor, 'SELECT id FROM hosts WHERE engagement_id = ?', e))
    _delete_reports(cursor, _ids(cursor, 'SELECT id FROM reports WHERE engagement_id = ?', e))
    _delete_maps(cursor, _ids(cursor, 'SELECT id FROM attack_maps WHERE engagement_id = ?', e))
    # Templates have no engagement; only this engagement's own plans go
    _delete_plans(cursor, _ids(cursor, 'SELECT id FROM test_plans WHERE engagement_id = ?', e))
    for table in _DIRECT:
        cursor.execute(f'DELETE FROM {table} WHERE engagement_id = ?', e)
    cursor.execute('DELETE FROM engagements WHERE id = ?', e)


def remove_upload_folder(upload_folder, engagement_id):
    """Delete uploads/<engagement_id>/ (after the delete is committed)."""
    root = os.path.realpath(upload_folder)
    folder = os.path.realpath(os.path.join(root, str(int(engagement_id))))
    if os.path.dirname(folder) != root or not os.path.isdir(folder):
        return
    try:
        shutil.rmtree(folder)
    except OSError as e:
        logger.warning('Could not remove the upload folder of deleted engagement %s: %s', engagement_id, e)


def purge_orphans(cursor):
    """Delete rows left behind by earlier, incomplete deletes; return how many.

    Rows are orphans when the engagement (or the parent row) they belong to no
    longer exists. Test plan templates (no engagement) are kept.
    """
    before = cursor.connection.total_changes
    sources = ['hosts', 'evidence', 'reports', 'attack_maps', 'test_plans', *_DIRECT]
    union = ' UNION '.join(f'SELECT engagement_id FROM {t}' for t in sources)
    gone = _ids(cursor, f'SELECT DISTINCT engagement_id FROM ({union}) WHERE engagement_id IS NOT NULL '
                        f'AND engagement_id NOT IN (SELECT id FROM engagements)')
    for engagement_id in gone:
        delete_engagement(cursor, engagement_id)
    # Children whose parent row is gone
    delete_evidence_rows(cursor, _ids(cursor,
        'SELECT evidence_id FROM evidence_tags WHERE evidence_id NOT IN (SELECT id FROM evidence) '
        'UNION SELECT evidence_id FROM evidence_hosts WHERE evidence_id NOT IN (SELECT id FROM evidence)'))
    _delete_hosts(cursor, _ids(cursor, ' UNION '.join(
        f'SELECT host_id FROM {t} WHERE host_id NOT IN (SELECT id FROM hosts)'
        for t in ('host_notes', 'host_ports', 'host_credentials', 'evidence_hosts'))))
    _delete_reports(cursor, _ids(cursor,
        'SELECT report_id FROM report_sections WHERE report_id NOT IN (SELECT id FROM reports)'))
    _delete_maps(cursor, _ids(cursor,
        'SELECT map_id FROM attack_map_nodes WHERE map_id NOT IN (SELECT id FROM attack_maps) '
        'UNION SELECT map_id FROM attack_map_edges WHERE map_id NOT IN (SELECT id FROM attack_maps)'))
    _delete_plans(cursor, _ids(cursor,
        'SELECT test_plan_id FROM test_plan_items WHERE test_plan_id NOT IN (SELECT id FROM test_plans)'))
    removed = cursor.connection.total_changes - before
    if gone or removed:
        logger.info('Removed %d row(s) left by deleted engagements %s', removed, gone)
    return removed

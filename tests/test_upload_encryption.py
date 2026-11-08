"""Uploaded evidence is encrypted at rest with the database key (retest M-14).

While the database is encrypted, evidence files are stored as a SecretBox under
a per-file key derived from the in-memory database key, created 0600 in 0700
folders, and cannot be read while the database is locked. Plaintext files from
before are encrypted on the first unlock. The route tests stand in for "the
database is encrypted and unlocked" by giving the store a key; the end-to-end
run with SQLCipher is in tests/test_setup_encryption.py.
"""

import io
import os
import stat

import pytest

from config import Config
from models import encryption, upload_store
from tests.conftest import ENGAGEMENT_A

KEY = 'ab' * 32
SECRET = b'Hunter2-ACME loot'
NESSUS = b"""<?xml version="1.0"?>
<NessusClientData_v2><Report name="r"><ReportHost name="10.9.9.9">
<HostProperties><tag name="host-ip">10.9.9.9</tag></HostProperties>
<ReportItem port="445" protocol="tcp" svc_name="cifs" severity="3" pluginID="1" pluginName="SMB signing">
<description>d</description></ReportItem></ReportHost></Report></NessusClientData_v2>"""


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture
def unlocked(monkeypatch):
    """The database is encrypted and unlocked, as far as the upload store can tell."""
    state = {'key': KEY}

    def database_key():
        if state['key'] is None:
            raise encryption.DatabaseLocked('locked')
        return state['key']
    monkeypatch.setattr(upload_store, '_database_key', database_key)
    return state


# ------------------------------------------------------------------ the store

def test_files_are_sealed_bound_to_their_path_and_private(tmp_path, unlocked):
    path = tmp_path / '1' / '5_loot.txt'
    upload_store.write_file(str(path), '1/5_loot.txt', SECRET)
    raw = path.read_bytes()
    assert raw.startswith(upload_store.MAGIC) and SECRET not in raw
    assert _mode(path) == 0o600 and _mode(path.parent) == 0o700
    assert upload_store.read_file(str(path), '1/5_loot.txt') == SECRET
    assert not list(tmp_path.rglob('*.ptvault-tmp'))

    with pytest.raises(upload_store.UploadDecryptError):          # moved to another record's path
        upload_store.read_file(str(path), '1/6_other.txt')
    unlocked['key'] = 'cd' * 32
    with pytest.raises(upload_store.UploadDecryptError):          # another database's key
        upload_store.read_file(str(path), '1/5_loot.txt')
    unlocked['key'] = None
    with pytest.raises(encryption.DatabaseLocked):                # locked: nothing reads it
        upload_store.read_file(str(path), '1/5_loot.txt')


def test_tampering_is_detected(tmp_path, unlocked):
    path = tmp_path / '1' / 'f.txt'
    upload_store.write_file(str(path), '1/f.txt', SECRET)
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(bytes(raw))
    with pytest.raises(upload_store.UploadDecryptError):
        upload_store.read_file(str(path), '1/f.txt')


def test_without_database_encryption_files_stay_plain_but_private(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_store, '_database_key', lambda: None)
    path = tmp_path / '1' / 'f.txt'
    upload_store.write_file(str(path), '1/f.txt', SECRET)
    assert path.read_bytes() == SECRET and _mode(path) == 0o600 and _mode(path.parent) == 0o700


def test_existing_files_are_encrypted_once_and_decrypted_on_disable(tmp_path, unlocked):
    (tmp_path / '1').mkdir()
    (tmp_path / '1' / 'a.txt').write_bytes(SECRET)
    (tmp_path / '2').mkdir()
    (tmp_path / '2' / 'b.png').write_bytes(b'\x89PNG' + SECRET)
    os.chmod(tmp_path / '1' / 'a.txt', 0o644)
    os.chmod(tmp_path / '1', 0o755)

    assert upload_store.encrypt_existing(str(tmp_path)) == 2
    for rel in ('1/a.txt', '2/b.png'):
        assert upload_store.is_sealed(str(tmp_path / rel)) and _mode(tmp_path / rel) == 0o600
    assert _mode(tmp_path / '1') == 0o700 and _mode(tmp_path) == 0o700
    assert upload_store.read_file(str(tmp_path / '2' / 'b.png'), '2/b.png') == b'\x89PNG' + SECRET
    assert upload_store.encrypt_existing(str(tmp_path)) == 0      # repeat: nothing to do

    assert upload_store.decrypt_existing(str(tmp_path)) == 2
    assert (tmp_path / '1' / 'a.txt').read_bytes() == SECRET


def test_nothing_is_encrypted_while_the_database_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_store, '_database_key', lambda: None)
    (tmp_path / '1').mkdir()
    (tmp_path / '1' / 'a.txt').write_bytes(SECRET)
    assert upload_store.encrypt_existing(str(tmp_path)) == 0
    assert (tmp_path / '1' / 'a.txt').read_bytes() == SECRET


# ------------------------------------------------------------------ the routes

def _editor(live):
    return live.client_for('editor', active_engagement=ENGAGEMENT_A)


def _upload(client, data, name, evidence_type='screenshot'):
    resp = client.post('/api/evidence', data={'evidence_type': evidence_type, 'title': 't',
                                              'file': (io.BytesIO(data), name)},
                       content_type='multipart/form-data')
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _stored(live, evidence_id):
    conn = live.db()
    rel = conn.execute('SELECT file_path FROM evidence WHERE id = ?', (evidence_id,)).fetchone()[0]
    conn.close()
    return os.path.join(Config.UPLOAD_FOLDER, rel)


def test_an_upload_is_encrypted_on_disk_and_served_decrypted(live_app, unlocked):
    client = _editor(live_app)
    ev = _upload(client, SECRET, 'loot.txt', 'other')
    path = _stored(live_app, ev['id'])
    raw = open(path, 'rb').read()
    assert SECRET not in raw and raw.startswith(upload_store.MAGIC)
    assert _mode(path) == 0o600 and _mode(os.path.dirname(path)) == 0o700

    download = client.get(f"/api/evidence/{ev['id']}/download")
    assert download.status_code == 200 and download.data == SECRET
    assert 'attachment' in download.headers['Content-Disposition']
    png = _upload(client, b'\x89PNG\r\n' + SECRET, 'shot.png')
    inline = client.get(f"/api/evidence/{png['id']}/file")
    assert inline.status_code == 200 and inline.data == b'\x89PNG\r\n' + SECRET
    assert inline.mimetype == 'image/png'


def test_a_locked_database_serves_no_evidence(live_app, unlocked):
    client = _editor(live_app)
    ev = _upload(client, SECRET, 'loot.txt', 'other')
    unlocked['key'] = None
    for suffix in ('download', 'file'):
        resp = client.get(f"/api/evidence/{ev['id']}/{suffix}")
        assert resp.status_code == 503 and SECRET not in resp.data


def test_a_file_that_does_not_open_is_an_error_not_ciphertext(live_app, unlocked):
    client = _editor(live_app)
    ev = _upload(client, SECRET, 'loot.txt', 'other')
    unlocked['key'] = 'cd' * 32
    resp = client.get(f"/api/evidence/{ev['id']}/download")
    assert resp.status_code == 500 and upload_store.MAGIC not in resp.data


def test_scans_are_still_parsed_from_an_encrypted_upload(live_app, unlocked):
    client = _editor(live_app)
    ev = _upload(client, NESSUS, 'scan.nessus', 'tool_output')
    assert not open(_stored(live_app, ev['id']), 'rb').read().startswith(b'<?xml')
    conn = live_app.db()
    meta = conn.execute('SELECT metadata FROM evidence WHERE id = ?', (ev['id'],)).fetchone()[0]
    hosts = conn.execute("SELECT COUNT(*) FROM hosts WHERE ip = '10.9.9.9'").fetchone()[0]
    conn.close()
    assert meta and 'nessus' in meta and hosts == 1
    assert client.post(f"/api/evidence/{ev['id']}/parse").status_code == 200

    nmap = open(os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_nmap.xml'), 'rb').read()
    scan = _upload(client, nmap, 'scan.xml', 'tool_output')
    conn = live_app.db()
    meta = conn.execute('SELECT metadata FROM evidence WHERE id = ?', (scan['id'],)).fetchone()[0]
    conn.close()
    assert meta and '"nmap"' in meta


def test_deleting_evidence_removes_the_encrypted_file(live_app, unlocked):
    client = _editor(live_app)
    ev = _upload(client, SECRET, 'loot.txt', 'other')
    path = _stored(live_app, ev['id'])
    assert client.delete(f"/api/evidence/{ev['id']}").status_code == 204
    assert not os.path.exists(path)


# ------------------------------------------------------------------ the folder

def test_the_upload_folder_follows_the_database(monkeypatch):
    from config import default_upload_folder
    monkeypatch.delenv('PTVAULT_UPLOAD_FOLDER', raising=False)
    assert default_upload_folder('/srv/ptvault/db/ptvault.db') == '/srv/ptvault/db/uploads'
    monkeypatch.setenv('PTVAULT_UPLOAD_FOLDER', '/mnt/evidence')
    assert default_upload_folder('/srv/ptvault/db/ptvault.db') == '/mnt/evidence'


def test_files_left_in_the_old_folder_are_reported(tmp_path, monkeypatch):
    old, new = tmp_path / 'app' / 'data' / 'uploads', tmp_path / 'db' / 'uploads'
    (old / '1').mkdir(parents=True)
    (old / '1' / 'a.txt').write_bytes(SECRET)
    monkeypatch.setattr(Config, 'LEGACY_UPLOAD_FOLDER', str(old))
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(new))
    assert str(old) in upload_store.legacy_upload_folder_warning()
    (new / '1').mkdir(parents=True)
    (new / '1' / 'a.txt').write_bytes(SECRET)
    assert upload_store.legacy_upload_folder_warning() is None


def test_every_folder_created_for_an_upload_is_private(tmp_path, unlocked):
    root = tmp_path / 'uploads'                                    # does not exist yet
    upload_store.write_file(str(root / '7' / 'f.txt'), '7/f.txt', SECRET)
    assert _mode(root) == 0o700 and _mode(root / '7') == 0o700

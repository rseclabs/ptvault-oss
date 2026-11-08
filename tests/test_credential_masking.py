"""M-9: harvested credentials are masked by default.

Lists, create/update responses and the relationship graph never carry a
password or hash. Editors and above can reveal one secret at a time through an
audited endpoint; the JSON export includes secrets only for editors.
"""

import pytest

from tests.conftest import ENGAGEMENT_A

HOST_SECRET = 'Host-Pa55word!'
ENG_SECRET = 'aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0'


@pytest.fixture
def creds(live_app):
    conn = live_app.db()
    host = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.0.0.9')", (ENGAGEMENT_A,)).lastrowid
    host_cred = conn.execute(
        "INSERT INTO host_credentials (host_id, username, password, password_type) VALUES (?, 'root', ?, 'cleartext')",
        (host, HOST_SECRET)).lastrowid
    eng_cred = conn.execute(
        "INSERT INTO engagement_credentials (engagement_id, username, password_or_hash, credential_type) "
        "VALUES (?, 'administrator', ?, 'ntlm')", (ENGAGEMENT_A, ENG_SECRET)).lastrowid
    conn.commit()
    conn.close()
    live_app.host, live_app.host_cred, live_app.eng_cred = host, host_cred, eng_cred
    return live_app


def _no_secret(resp):
    body = resp.get_data(as_text=True)
    return HOST_SECRET not in body and ENG_SECRET not in body and ENG_SECRET[:20] not in body


@pytest.mark.parametrize('user', ['viewer', 'editor', 'owner', 'admin'])
def test_credential_lists_are_masked(creds, user):
    client = creds.client_for(user, active_engagement=ENGAGEMENT_A)
    eng = client.get(f'/api/engagements/{ENGAGEMENT_A}/credentials')
    host = client.get(f'/api/hosts/{creds.host}/credentials')
    assert eng.status_code == 200 and host.status_code == 200
    assert _no_secret(eng) and _no_secret(host)
    assert all(c['has_secret'] for c in eng.get_json())
    host_list = host.get_json()
    host_list = host_list.get('credentials', host_list) if isinstance(host_list, dict) else host_list
    assert all(c['has_secret'] for c in host_list)


def test_create_and_update_responses_are_masked(creds):
    client = creds.client_for('editor', active_engagement=ENGAGEMENT_A)
    created = client.post(f'/api/engagements/{ENGAGEMENT_A}/credentials',
                          json={'username': 'svc', 'password_or_hash': ENG_SECRET})
    assert created.status_code == 201 and _no_secret(created)
    updated = client.put(f'/api/hosts/{creds.host}/credentials/{creds.host_cred}',
                         json={'password': HOST_SECRET, 'notes': 'n'})
    assert updated.status_code == 200 and _no_secret(updated)


def test_update_without_password_keeps_it(creds):
    client = creds.client_for('editor', active_engagement=ENGAGEMENT_A)
    assert client.put(f'/api/engagements/{ENGAGEMENT_A}/credentials/{creds.eng_cred}',
                      json={'description': 'kept'}).status_code == 200
    assert client.put(f'/api/hosts/{creds.host}/credentials/{creds.host_cred}',
                      json={'notes': 'kept'}).status_code == 200
    conn = creds.db()
    assert conn.execute('SELECT password_or_hash FROM engagement_credentials').fetchone()[0] == ENG_SECRET
    assert conn.execute('SELECT password FROM host_credentials').fetchone()[0] == HOST_SECRET
    conn.close()


def _reveals(live):
    conn = live.db()
    rows = conn.execute("SELECT user_id, resource_type, resource_id FROM audit_log WHERE action = 'view'").fetchall()
    conn.close()
    return [tuple(r) for r in rows]


def test_editor_can_reveal_and_reveals_are_audited(creds):
    client = creds.client_for('editor', active_engagement=ENGAGEMENT_A)
    eng = client.get(f'/api/engagements/{ENGAGEMENT_A}/credentials/{creds.eng_cred}/secret')
    host = client.get(f'/api/hosts/{creds.host}/credentials/{creds.host_cred}/secret')
    assert eng.get_json() == {'secret': ENG_SECRET}
    assert host.get_json() == {'secret': HOST_SECRET}
    editor = creds.user_ids['editor']
    assert sorted(_reveals(creds)) == sorted([
        (editor, 'engagement_credential', creds.eng_cred), (editor, 'host_credential', creds.host_cred)])


@pytest.mark.parametrize('user,expected', [('viewer', 403), ('outsider', 404)])
def test_reveal_is_refused_below_editor(creds, user, expected):
    client = creds.client_for(user, active_engagement=ENGAGEMENT_A)
    eng = client.get(f'/api/engagements/{ENGAGEMENT_A}/credentials/{creds.eng_cred}/secret')
    host = client.get(f'/api/hosts/{creds.host}/credentials/{creds.host_cred}/secret')
    assert eng.status_code == expected
    assert host.status_code in (403, 400)  # the outsider's session has no active engagement
    assert _no_secret(eng) and _no_secret(host)
    assert _reveals(creds) == []


def test_reveal_rejects_credential_from_another_host(creds):
    conn = creds.db()
    other_host = conn.execute("INSERT INTO hosts (engagement_id, ip) VALUES (?, '10.0.0.10')",
                              (ENGAGEMENT_A,)).lastrowid
    conn.commit()
    conn.close()
    client = creds.client_for('editor', active_engagement=ENGAGEMENT_A)
    assert client.get(f'/api/hosts/{other_host}/credentials/{creds.host_cred}/secret').status_code == 404


@pytest.mark.parametrize('user,includes', [('viewer', False), ('editor', True)])
def test_json_export_includes_secrets_only_for_editors(creds, user, includes):
    client = creds.client_for(user, active_engagement=ENGAGEMENT_A)
    resp = client.get(f'/api/engagements/{ENGAGEMENT_A}/export/json')
    assert resp.status_code == 200
    assert (not _no_secret(resp)) == includes


def test_graph_titles_never_contain_secrets(creds):
    client = creds.client_for('editor', active_engagement=ENGAGEMENT_A)
    resp = client.get('/api/relationships/graph')
    assert resp.status_code == 200
    assert _no_secret(resp)

"""Tests for ClientDAO."""

from models.dao.client_dao import ClientDAO


def test_create_and_find_by_id(app_ctx):
    dao = ClientDAO()
    new_id = dao.create({
        'name': 'ACME Corp',
        'admin_contact_email': 'admin@acme.com',
        'website': 'https://acme.com',
    })
    assert new_id > 0

    client = dao.find_by_id(new_id)
    assert client is not None
    assert client['name'] == 'ACME Corp'
    assert client['admin_contact_email'] == 'admin@acme.com'
    assert client['website'] == 'https://acme.com'


def test_find_by_name_is_case_insensitive(app_ctx):
    dao = ClientDAO()
    dao.create({'name': 'ACME Corp'})

    assert dao.find_by_name('acme corp') is not None
    assert dao.find_by_name('ACME CORP') is not None
    assert dao.find_by_name('  ACME Corp  ') is not None
    assert dao.find_by_name('Globex') is None


def test_list_options_returns_id_and_name_only(app_ctx):
    dao = ClientDAO()
    dao.create({'name': 'Beta Co', 'address': 'Secret HQ'})
    dao.create({'name': 'Alpha Co', 'notes': 'Internal notes'})

    options = dao.list_options()
    names = [o['name'] for o in options]
    assert names == ['Alpha Co', 'Beta Co']  # ordered by name
    # PII fields stripped
    for opt in options:
        assert set(opt.keys()) == {'id', 'name'}


def test_count_engagements_zero_for_unused_client(app_ctx):
    dao = ClientDAO()
    cid = dao.create({'name': 'Unused Co'})
    assert dao.count_engagements(cid) == 0


def test_count_engagements_reflects_links(app_ctx):
    dao = ClientDAO()
    cid = dao.create({'name': 'Linked Co'})

    cursor = app_ctx.cursor()
    cursor.execute(
        "INSERT INTO engagements (name, client_name, client_id) VALUES (?, ?, ?)",
        ('Eng A', 'Linked Co', cid),
    )
    cursor.execute(
        "INSERT INTO engagements (name, client_name, client_id) VALUES (?, ?, ?)",
        ('Eng B', 'Linked Co', cid),
    )
    app_ctx.commit()

    assert dao.count_engagements(cid) == 2


def test_update_changes_persist(app_ctx):
    dao = ClientDAO()
    cid = dao.create({'name': 'OldName'})
    dao.update(cid, {'name': 'NewName', 'address': '1 New St'})

    refreshed = dao.find_by_id(cid)
    assert refreshed['name'] == 'NewName'
    assert refreshed['address'] == '1 New St'


def test_delete_removes_row(app_ctx):
    dao = ClientDAO()
    cid = dao.create({'name': 'Doomed Co'})
    assert dao.find_by_id(cid) is not None

    dao.delete(cid)
    assert dao.find_by_id(cid) is None

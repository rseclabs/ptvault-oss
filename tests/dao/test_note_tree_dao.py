"""Tests for NoteTreeDAO.

Exercises tree behavior against the engagement_notes table; the same
DAO is used for host_notes with a different scope_column, so covering
one parameterization is enough to validate the logic.
"""

import pytest

from models.dao.note_tree_dao import NoteTreeDAO


@pytest.fixture
def dao(app_ctx):
    return NoteTreeDAO('engagement_notes', 'engagement_id')


@pytest.fixture
def engagement_id(app_ctx):
    """Insert a parent engagement so notes have a valid scope FK."""
    cur = app_ctx.cursor()
    cur.execute("INSERT INTO engagements (name) VALUES ('Test Eng')")
    app_ctx.commit()
    return cur.lastrowid


def test_create_root_returns_id(dao, engagement_id):
    nid = dao.create(engagement_id, 'root content')
    assert nid > 0


def test_create_child_under_parent(dao, engagement_id):
    parent = dao.create(engagement_id, 'parent')
    child = dao.create(engagement_id, 'child', parent_id=parent)

    note = dao.get_full(child, engagement_id)
    assert note['parent_id'] == parent
    assert note['content'] == 'child'


def test_default_sort_order_increments_per_parent(dao, engagement_id):
    a = dao.create(engagement_id, 'a')
    b = dao.create(engagement_id, 'b')
    c = dao.create(engagement_id, 'c')
    rows = dao.list_for(engagement_id)
    by_id = {r['id']: r for r in rows}
    # Each root note gets a strictly increasing sort_order
    assert by_id[a]['sort_order'] < by_id[b]['sort_order'] < by_id[c]['sort_order']


def test_list_for_orders_roots_first_then_children(dao, engagement_id):
    root = dao.create(engagement_id, 'root')
    child = dao.create(engagement_id, 'child', parent_id=root)
    rows = dao.list_for(engagement_id)
    ids = [r['id'] for r in rows]
    assert ids.index(root) < ids.index(child)


def test_count_children(dao, engagement_id):
    parent = dao.create(engagement_id, 'p')
    assert dao.count_children(parent, engagement_id) == 0
    dao.create(engagement_id, 'c1', parent_id=parent)
    dao.create(engagement_id, 'c2', parent_id=parent)
    assert dao.count_children(parent, engagement_id) == 2


def test_move_to_new_parent(dao, engagement_id):
    a = dao.create(engagement_id, 'a')
    b = dao.create(engagement_id, 'b')
    leaf = dao.create(engagement_id, 'leaf', parent_id=a)

    dao.move(leaf, engagement_id, new_parent_id=b, new_sort_order=None)
    assert dao.get_full(leaf, engagement_id)['parent_id'] == b


def test_move_to_root(dao, engagement_id):
    parent = dao.create(engagement_id, 'p')
    child = dao.create(engagement_id, 'c', parent_id=parent)
    dao.move(child, engagement_id, new_parent_id=None, new_sort_order=None)
    assert dao.get_full(child, engagement_id)['parent_id'] is None


def test_move_rejects_self_parent(dao, engagement_id):
    nid = dao.create(engagement_id, 'me')
    with pytest.raises(ValueError, match='own parent'):
        dao.move(nid, engagement_id, new_parent_id=nid, new_sort_order=None)


def test_move_rejects_descendant_as_parent(dao, engagement_id):
    """Moving a note into its own subtree must fail (cycle prevention)."""
    grandparent = dao.create(engagement_id, 'gp')
    parent = dao.create(engagement_id, 'p', parent_id=grandparent)
    child = dao.create(engagement_id, 'c', parent_id=parent)

    with pytest.raises(ValueError, match='subtree'):
        dao.move(grandparent, engagement_id, new_parent_id=child, new_sort_order=None)


def test_move_rejects_parent_from_different_scope(dao, app_ctx, engagement_id):
    """parent_belongs_to_scope guard: can't reach into another engagement."""
    # Second engagement with its own note
    cur = app_ctx.cursor()
    cur.execute("INSERT INTO engagements (name) VALUES ('Other')")
    other_eng = cur.lastrowid
    app_ctx.commit()
    other_note = dao.create(other_eng, 'other')

    nid = dao.create(engagement_id, 'mine')
    with pytest.raises(ValueError, match='not found'):
        dao.move(nid, engagement_id, new_parent_id=other_note, new_sort_order=None)


def test_create_rejects_parent_from_different_scope(dao, app_ctx, engagement_id):
    cur = app_ctx.cursor()
    cur.execute("INSERT INTO engagements (name) VALUES ('Other')")
    other_eng = cur.lastrowid
    app_ctx.commit()
    other_note = dao.create(other_eng, 'other')

    # parent_belongs_to_scope is a check the route uses; verify it does
    # what we expect when called directly.
    assert dao.parent_belongs_to_scope(other_note, engagement_id) is False
    assert dao.parent_belongs_to_scope(other_note, other_eng) is True
    assert dao.parent_belongs_to_scope(None, engagement_id) is True


def test_update_content_updates_row(dao, engagement_id):
    nid = dao.create(engagement_id, 'before')
    assert dao.update_content(nid, engagement_id, 'after') is True
    assert dao.get_full(nid, engagement_id)['content'] == 'after'


def test_update_content_returns_false_for_wrong_scope(dao, app_ctx, engagement_id):
    cur = app_ctx.cursor()
    cur.execute("INSERT INTO engagements (name) VALUES ('Other')")
    other = cur.lastrowid
    app_ctx.commit()

    nid = dao.create(engagement_id, 'mine')
    assert dao.update_content(nid, other, 'hijack') is False
    # Original content stays
    assert dao.get_full(nid, engagement_id)['content'] == 'mine'


def test_delete_removes_row(dao, engagement_id):
    nid = dao.create(engagement_id, 'doomed')
    assert dao.delete(nid, engagement_id) is True
    assert dao.get_full(nid, engagement_id) is None


def test_list_preview_truncation(dao, engagement_id):
    """Long content gets truncated; has_more flag set."""
    long_content = 'x' * 600  # > PREVIEW_CHARS (500)
    short_content = 'short'
    long_id = dao.create(engagement_id, long_content)
    short_id = dao.create(engagement_id, short_content)

    rows = {r['id']: r for r in dao.list_for(engagement_id)}
    assert rows[long_id]['has_more'] is True
    assert len(rows[long_id]['content_preview']) == 500
    assert rows[short_id]['has_more'] is False
    assert rows[short_id]['content_preview'] == 'short'

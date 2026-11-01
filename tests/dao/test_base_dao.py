"""Tests for BaseDAO class.

Tests common CRUD operations and engagement-based data isolation.
"""

import pytest
import sqlite3
import tempfile
import os
from flask import Flask, g
from models.dao.base import BaseDAO


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def db_path():
    """Create temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def db_connection(db_path):
    """Create test database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Create test tables
    conn.execute('''
        CREATE TABLE test_items (
            id INTEGER PRIMARY KEY,
            engagement_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE global_items (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def dao(app, db_connection):
    """Create BaseDAO instance with test context."""
    with app.test_request_context():
        g.db = db_connection
        g.active_engagement_id = 1
        dao = BaseDAO('test_items', engagement_scoped=True)
        yield dao


@pytest.fixture
def global_dao(app, db_connection):
    """Create BaseDAO instance without engagement scoping."""
    with app.test_request_context():
        g.db = db_connection
        dao = BaseDAO('global_items', engagement_scoped=False)
        yield dao


class TestBaseDAOCreate:
    """Test create operations."""

    def test_create_with_engagement_scoping(self, dao):
        """Test creating record with automatic engagement_id."""
        record_id = dao.create({'name': 'Test Item', 'status': 'active'})

        assert record_id > 0

        # Verify record was created with engagement_id
        cursor = g.db.cursor()
        cursor.execute('SELECT * FROM test_items WHERE id = ?', (record_id,))
        row = cursor.fetchone()

        assert row['name'] == 'Test Item'
        assert row['status'] == 'active'
        assert row['engagement_id'] == 1

    def test_create_without_engagement_scoping(self, global_dao):
        """Test creating record without engagement scoping."""
        record_id = global_dao.create({'name': 'Global Item'})

        assert record_id > 0

        cursor = g.db.cursor()
        cursor.execute('SELECT * FROM global_items WHERE id = ?', (record_id,))
        row = cursor.fetchone()

        assert row['name'] == 'Global Item'


class TestBaseDAORead:
    """Test read operations."""

    def test_find_all_with_engagement_filter(self, dao):
        """Test finding all records filters by engagement."""
        # Create records for different engagements
        dao.create({'name': 'Item 1', 'status': 'active'})
        dao.create({'name': 'Item 2', 'status': 'inactive'})

        # Create record for different engagement
        cursor = g.db.cursor()
        cursor.execute('''
            INSERT INTO test_items (engagement_id, name, status)
            VALUES (2, 'Item 3', 'active')
        ''')
        g.db.commit()

        # Find all should only return items from engagement 1
        items = dao.find_all()

        assert len(items) == 2
        assert all(item['engagement_id'] == 1 for item in items)

    def test_find_all_with_filters(self, dao):
        """Test finding records with additional filters."""
        dao.create({'name': 'Active Item', 'status': 'active'})
        dao.create({'name': 'Inactive Item', 'status': 'inactive'})

        active_items = dao.find_all({'status': 'active'})

        assert len(active_items) == 1
        assert active_items[0]['name'] == 'Active Item'

    def test_find_all_with_pagination(self, dao):
        """Test pagination with limit and offset."""
        for i in range(10):
            dao.create({'name': f'Item {i}', 'status': 'active'})

        # Get first page
        page1 = dao.find_all(limit=3, offset=0)
        assert len(page1) == 3

        # Get second page
        page2 = dao.find_all(limit=3, offset=3)
        assert len(page2) == 3
        assert page2[0]['id'] != page1[0]['id']

    def test_find_by_id_with_engagement_filter(self, dao):
        """Test finding by ID respects engagement isolation."""
        record_id = dao.create({'name': 'Test Item', 'status': 'active'})

        # Should find record in same engagement
        item = dao.find_by_id(record_id)
        assert item is not None
        assert item['name'] == 'Test Item'

        # Change engagement context
        g.active_engagement_id = 2

        # Should NOT find record from different engagement
        item = dao.find_by_id(record_id)
        assert item is None

    def test_find_one(self, dao):
        """Test finding single record by filters."""
        dao.create({'name': 'Unique Item', 'status': 'active'})

        item = dao.find_one({'name': 'Unique Item'})

        assert item is not None
        assert item['status'] == 'active'

    def test_count(self, dao):
        """Test counting records."""
        dao.create({'name': 'Item 1', 'status': 'active'})
        dao.create({'name': 'Item 2', 'status': 'active'})
        dao.create({'name': 'Item 3', 'status': 'inactive'})

        # Count all
        total = dao.count()
        assert total == 3

        # Count with filter
        active_count = dao.count({'status': 'active'})
        assert active_count == 2

    def test_exists(self, dao):
        """Test checking if record exists."""
        assert dao.exists({'name': 'Nonexistent'}) is False

        dao.create({'name': 'Exists', 'status': 'active'})

        assert dao.exists({'name': 'Exists'}) is True


class TestBaseDAOUpdate:
    """Test update operations."""

    def test_update_with_engagement_filter(self, dao):
        """Test updating record respects engagement isolation."""
        record_id = dao.create({'name': 'Test Item', 'status': 'active'})

        # Update should succeed in same engagement
        success = dao.update(record_id, {'status': 'completed'})
        assert success is True

        item = dao.find_by_id(record_id)
        assert item['status'] == 'completed'

        # Change engagement context
        g.active_engagement_id = 2

        # Update should fail in different engagement
        success = dao.update(record_id, {'status': 'failed'})
        assert success is False

    def test_update_multiple_fields(self, dao):
        """Test updating multiple fields at once."""
        record_id = dao.create({'name': 'Test Item', 'status': 'active'})

        dao.update(record_id, {
            'name': 'Updated Item',
            'status': 'completed'
        })

        item = dao.find_by_id(record_id)
        assert item['name'] == 'Updated Item'
        assert item['status'] == 'completed'

    def test_update_empty_data(self, dao):
        """Test update with empty data returns False."""
        record_id = dao.create({'name': 'Test Item', 'status': 'active'})

        success = dao.update(record_id, {})
        assert success is False


class TestBaseDAODelete:
    """Test delete operations."""

    def test_delete_with_engagement_filter(self, dao):
        """Test deleting record respects engagement isolation."""
        record_id = dao.create({'name': 'Test Item', 'status': 'active'})

        # Delete should succeed in same engagement
        success = dao.delete(record_id)
        assert success is True

        # Verify deleted
        item = dao.find_by_id(record_id)
        assert item is None

        # Create record and change engagement
        record_id = dao.create({'name': 'Test Item 2', 'status': 'active'})
        g.active_engagement_id = 2

        # Delete should fail in different engagement
        success = dao.delete(record_id)
        assert success is False

    def test_delete_nonexistent(self, dao):
        """Test deleting nonexistent record returns False."""
        success = dao.delete(9999)
        assert success is False


class TestEngagementIsolation:
    """Test data isolation between engagements."""

    def test_data_isolation(self, dao):
        """Test that operations only affect current engagement."""
        # Create records in engagement 1
        g.active_engagement_id = 1
        dao.create({'name': 'Item 1A', 'status': 'active'})
        dao.create({'name': 'Item 1B', 'status': 'active'})

        # Create records in engagement 2
        g.active_engagement_id = 2
        dao.create({'name': 'Item 2A', 'status': 'active'})
        dao.create({'name': 'Item 2B', 'status': 'active'})

        # Switch back to engagement 1
        g.active_engagement_id = 1
        items_1 = dao.find_all()

        # Switch to engagement 2
        g.active_engagement_id = 2
        items_2 = dao.find_all()

        # Verify isolation
        assert len(items_1) == 2
        assert len(items_2) == 2
        assert all('1' in item['name'] for item in items_1)
        assert all('2' in item['name'] for item in items_2)

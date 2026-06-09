"""
Shared pytest fixtures for all test layers.

- `client`  : Flask test client backed by a fresh temp SQLite DB (per test)
- `seeded_client` : same, but with hubs + routes pre-seeded (via db._seed_data)
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def client(tmp_path):
    import db
    import app as flask_app

    db_file = str(tmp_path / 'test.db')
    original = db.DB_PATH
    db.DB_PATH = db_file

    flask_app.app.config['TESTING'] = True
    db.init_db()

    with flask_app.app.test_client() as c:
        yield c

    db.DB_PATH = original
    if os.path.exists(db_file):
        os.unlink(db_file)


@pytest.fixture
def seeded_client(client):
    """client fixture that already has the default 25 hubs + 49 routes seeded."""
    return client

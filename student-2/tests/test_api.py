import os
import pytest

os.environ["DB_PATH"] = ":memory:"

from database import init_db, seed_db, get_db

@pytest.fixture(autouse=True)
def setup_test_db():
    conn = get_db()
    seed_db()
    yield
    conn.close()
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path):
    # throwaway db so tests never touch data/catalog.db
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")

    # reimport so the app picks up the new DATABASE_PATH and reseeds
    for module in ("backend.app", "database.db", "database.init_db"):
        sys.modules.pop(module, None)

    from backend.app import app

    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client

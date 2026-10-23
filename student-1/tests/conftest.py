import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # throwaway db so tests never touch data/catalog.db
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")

    # reimport so the app picks up the new DATABASE_PATH and reseeds
    for module in ("backend.app", "database.db", "database.init_db"):
        sys.modules.pop(module, None)

    import backend.app as catalog_app

    app = catalog_app.app
    # CI sets this false. Tests fake the server, so leave it on unless a test turns it off.
    monkeypatch.setattr(catalog_app, "MULTI_AGENT_ENABLED", True)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client

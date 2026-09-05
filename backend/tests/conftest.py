"""Test bootstrap: points every filesystem/DB/vector-store dependency at a
throwaway temp directory *before* any `app.*` module is imported, so tests
never touch the real `backend/chroma_data/`, `backend/knowledgebase/`, or a
real Postgres database.

Env vars must be set at module import time (not inside a fixture) because
`app/core/config.py` builds its `settings` singleton — and
`app/services/vectorstore/chroma_client.py` opens its persistent Chroma
client — the moment those modules are first imported, which for a fixture
would already be too late.
"""

import os
import shutil
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="tef_kb_test_"))
os.environ["CHROMA_PERSIST_DIR"] = str(_TEST_ROOT / "chroma_data")
os.environ["KB_DATA_DIR"] = str(_TEST_ROOT / "knowledgebase")
os.environ["FAQ_DATA_DIR"] = str(_TEST_ROOT / "faq")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT / 'test.db'}"
os.environ.setdefault("GROQ_API_KEY", "test-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.models import KnowledgeDocument  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services.vectorstore.chroma_client import knowledge_base  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _isolated_kb_state():
    """Every test starts and ends with an empty KB registry, empty Chroma
    knowledge_base collection, and empty knowledgebase/ folder, so tests
    never see documents left behind by another test."""
    yield

    db = SessionLocal()
    try:
        db.query(KnowledgeDocument).delete()
        db.commit()
    finally:
        db.close()

    existing_ids = knowledge_base.get()["ids"]
    if existing_ids:
        knowledge_base.delete(ids=existing_ids)

    kb_dir = Path(os.environ["KB_DATA_DIR"])
    if kb_dir.exists():
        shutil.rmtree(kb_dir)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)

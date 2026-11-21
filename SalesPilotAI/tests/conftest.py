from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.database import Database
from main import create_application


@pytest.fixture
def database():
    db = Database(":memory:")
    db.initialize()
    yield db
    db.close()


@pytest.fixture(scope="session")
def application():
    app = create_application([])
    yield app

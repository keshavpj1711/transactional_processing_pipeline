"""Test fixtures.

The API tests run against an in-memory SQLite database and execute Celery tasks
eagerly (synchronously, in-process) with the stub LLM, so the full upload ->
process -> results flow is exercised without Postgres, Redis, or a worker.
"""

import os

os.environ.setdefault("USE_STUB_LLM", "true")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db as db_module
from app.celery_app import celery_app
from app.db import Base, get_db


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    # Point both the request path and the (eager) task path at this database.
    db_module.SessionLocal = TestingSession
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    from app.main import app as fastapi_app

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()

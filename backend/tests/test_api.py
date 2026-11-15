from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from lina.api.main import app
from lina.config import Settings, get_settings
from lina.db import get_session


class _Result:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one(self) -> object:
        return self._value

    def scalar_one_or_none(self) -> object:
        return self._value


class _StubSession:
    """Stands in for a database session so tests need no Postgres."""

    def execute(self, statement: object) -> _Result:
        return _Result("0001" if "alembic_version" in str(statement) else 0)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: _StubSession()
    app.dependency_overrides[get_settings] = lambda: Settings(internal_api_token="test-token")
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_needs_no_auth(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_internal_rejects_missing_token(client: TestClient) -> None:
    assert client.get("/internal/status").status_code == 401


def test_internal_rejects_wrong_token(client: TestClient) -> None:
    response = client.get("/internal/status", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_internal_accepts_correct_token(client: TestClient) -> None:
    response = client.get("/internal/status", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["schema_revision"] == "0001"


def test_internal_fails_closed_when_token_unset(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(internal_api_token="")
    response = client.get("/internal/status", headers={"Authorization": "Bearer "})
    assert response.status_code == 503

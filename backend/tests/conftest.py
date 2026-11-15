import os
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from lina.config import Settings
from lina.models import Base
from lina.pipeline.http import PoliteClient

FIXTURES = Path(__file__).parent / "fixtures"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://lina:lina@localhost:5433/lina_test"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def settings() -> Settings:
    return Settings(bot_contact_url="https://lina.example/bot", fetch_delay_seconds=5.0)


class FakeWeb:
    """A pretend internet: canned responses, a clock that only moves when the
    client sleeps, and a record of every request. No test touches the network."""

    def __init__(self) -> None:
        self.pages: dict[str, httpx2.Response | Callable[[httpx2.Request], httpx2.Response]] = {}
        self.requests: list[httpx2.Request] = []
        self.sleeps: list[float] = []
        self.now = 1000.0

    def add(
        self,
        url: str,
        body: str = "",
        status: int = 200,
        content_type: str = "text/html; charset=utf-8",
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        headers = {"content-type": content_type}
        if etag:
            headers["etag"] = etag
        if last_modified:
            headers["last-modified"] = last_modified
        self.pages[url] = httpx2.Response(status, text=body, headers=headers)

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        page = self.pages.get(str(request.url))
        if page is None:
            return httpx2.Response(404, text="not found")
        if callable(page):
            return page(request)
        return httpx2.Response(page.status_code, content=page.content, headers=page.headers)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def urls(self) -> list[str]:
        return [str(request.url) for request in self.requests]

    def client(self, settings: Settings) -> PoliteClient:
        return PoliteClient(
            settings,
            transport=httpx2.MockTransport(self.handler),
            sleep=self.sleep,
            clock=lambda: self.now,
        )


@pytest.fixture
def web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """A throwaway `lina_test` database on the local Postgres (docker compose up -d db)."""
    url = make_url(TEST_DATABASE_URL)
    try:
        admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
        admin.dispose()
    except OperationalError:
        if os.environ.get("CI"):
            raise
        pytest.skip("Postgres is not running (docker compose up -d db)")
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after each test, even after commit()."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()

import os

import pytest

_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sentinel:CHANGE_ME@127.0.0.1:55432/paysentineliq",
)
_TEST_REDIS_URL = os.environ.get(
    "TEST_REDIS_URL",
    "redis://127.0.0.1:6379/0",
)

os.environ["APP_ENV"] = "local"
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
os.environ["REDIS_URL"] = _TEST_REDIS_URL


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-docker",
        action="store_true",
        default=False,
        help="run tests that require docker compose up",
    )
    parser.addoption(
        "--run-observability",
        action="store_true",
        default=False,
        help="run tests that require the observability compose profile",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--run-docker"):
        skip_docker = pytest.mark.skip(
            reason="requires --run-docker and docker compose up",
        )
        for item in items:
            if "docker" in item.keywords:
                item.add_marker(skip_docker)
    if not config.getoption("--run-observability"):
        skip_observability = pytest.mark.skip(
            reason="requires --run-observability and the observability profile",
        )
        for item in items:
            if "observability" in item.keywords:
                item.add_marker(skip_observability)

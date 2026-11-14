import os

import pytest

_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sentinel:CHANGE_ME@localhost:55432/paysentineliq",
)
_TEST_REDIS_URL = os.environ.get(
    "TEST_REDIS_URL",
    "redis://localhost:6379/0",
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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-docker"):
        return

    skip_docker = pytest.mark.skip(reason="requires --run-docker and docker compose up")
    for item in items:
        if "docker" in item.keywords:
            item.add_marker(skip_docker)

import os
import re
from pathlib import Path

import pytest

from harness import Session

HERE = Path(__file__).resolve().parent


def pytest_addoption(parser):
    parser.addoption("--artifacts", default=os.environ.get("SESSION_ARTIFACTS", "artifacts"),
                     help="directory for sway logs, screenshots and the JUnit report")
    parser.addoption("--invert-negative", action="store_true",
                     help="flip the negative test's assertion; it must then FAIL (proves assertions assert)")


@pytest.fixture
def artifacts_dir(request):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.nodeid)
    path = Path(request.config.getoption("--artifacts")) / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def session_config():
    """The sway config a profile's tests run under. Profiles override this in their conftest.py."""
    return HERE / "configs" / "stock.conf"


@pytest.fixture
def session(session_config, artifacts_dir):
    """A fresh headless sway per test; logs and screenshots land in artifacts_dir."""
    s = Session(session_config, artifacts_dir).start()
    try:
        yield s
    finally:
        s.stop()


@pytest.fixture
def invert_negative(request):
    return request.config.getoption("--invert-negative")

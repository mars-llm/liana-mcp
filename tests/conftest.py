import hashlib

import pytest

from liana_mcp.config import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings(tmp_path):
    binary = tmp_path / "pinned-placeholder"
    binary.write_bytes(b"not executed in unit tests")
    binary.chmod(0o700)
    pin = {"path": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    state = tmp_path / "state"
    return Settings(state_directory=str(state), core=pin, lianad=pin)


@pytest.fixture(autouse=True)
def disable_telemetry(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

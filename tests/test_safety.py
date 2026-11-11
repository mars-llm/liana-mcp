import json
from types import SimpleNamespace

import pytest
from mcp import MCPError
from pydantic import ValidationError

from liana_mcp.config import Settings, private_directory, private_file
from liana_mcp.errors import SafetyError
from liana_mcp.rpc import RPCError, decode
from liana_mcp.runtime import Run, Runtime, write_json
from liana_mcp.server import InputGate


@pytest.mark.parametrize("field", ["network", "rpc_url", "shell", "seed", "wallet_path"])
def test_no_model_selectable_runtime_configuration(settings, field):
    data = settings.model_dump()
    data[field] = "not allowed"
    with pytest.raises(ValidationError):
        Settings.model_validate(data)


def test_default_is_read_only(settings):
    runtime = Runtime(settings)
    with pytest.raises(SafetyError, match="disabled"), runtime.operation(mutate=True):
        pytest.fail("Mutating body must not run")


def test_binary_pins_and_permissions(settings):
    path = settings.core.checked()
    path.write_bytes(b"changed")
    with pytest.raises(SafetyError, match="integrity"):
        settings.core.checked()
    path.chmod(0o777)
    with pytest.raises(SafetyError, match="another user"):
        settings.core.checked()


def test_symlink_and_public_files_are_refused(tmp_path):
    path = tmp_path / "private.json"
    write_json(path, {"sensitive": "local-only"})
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(SafetyError):
        private_file(link)
    with pytest.raises(SafetyError):
        write_json(link, {})
    assert json.loads(private_file(path)) == {"sensitive": "local-only"}
    path.chmod(0o644)
    with pytest.raises(SafetyError):
        private_file(path)


def test_directory_symlink_and_permissions(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    link = tmp_path / "alias"
    link.symlink_to(directory)
    with pytest.raises(SafetyError):
        private_directory(link)
    directory.chmod(0o755)
    with pytest.raises(SafetyError):
        private_directory(directory)


def test_cross_instance_lock(settings):
    first, second = Runtime(settings), Runtime(settings)
    with first.operation():
        with pytest.raises(SafetyError, match="Another operation"), second.operation():
            pytest.fail("Concurrent operation entered")
    with second.operation():
        assert second.public_status()["status"] == "not_started"


@pytest.mark.parametrize("handle", ["../outside", "/other", "a" * 33, "g" * 32, ""])
def test_run_handles_are_not_paths(handle):
    with pytest.raises(ValidationError):
        Run(
            run=handle,
            rpc_port=1234,
            descriptor_sha256="a" * 64,
            core_sha256="a" * 64,
            lianad_sha256="b" * 64,
            gui_language="en",
        )


@pytest.mark.parametrize(
    "reply",
    [
        b"not JSON",
        b"[]",
        b'{"id":"wrong","result":{}}',
        b'{"id":"id"}',
        b'{"id":"id","error":"secret"}',
    ],
)
def test_rpc_rejects_invalid_framing_and_identity(reply):
    with pytest.raises(SafetyError):
        decode(reply, "id")


def test_rpc_errors_do_not_echo_backend_messages():
    with pytest.raises(RPCError) as result:
        decode(b'{"id":"id","error":{"code":-28,"message":"private-sentinel"}}', "id")
    assert result.value.code == -28
    assert "private-sentinel" not in str(result.value)


@pytest.mark.anyio
async def test_rate_limit_is_enforced():
    gate = InputGate()
    gate.tokens = 0
    gate.last += 1  # deterministic exhausted bucket without sleeping
    ctx = SimpleNamespace(
        method="tools/call", protocol_version="2026-07-28", params={"name": "liana_demo_status"}
    )

    async def should_not_run(ctx):
        pytest.fail("Rate-limited handler executed")

    with pytest.raises(MCPError, match="Too many"):
        await gate(ctx, should_not_run)

import json

import pytest
from mcp import Client

from liana_mcp.approval import approve, consume
from liana_mcp.errors import SafetyError
from liana_mcp.runtime import Runtime, write_json
from liana_mcp.server import create_server


@pytest.mark.anyio
async def test_setup_requires_independent_operator_permit(settings):
    settings.enable_regtest_mutations = True
    settings.require_operator_approval = True
    runtime = Runtime(settings)
    async with Client(create_server(runtime)) as client:
        result = await client.call_tool("setup_liana_demo", {})
        assert result.is_error
        assert "local operator approval" in json.dumps(result.model_dump())
    assert not runtime.state_file.exists()
    assert not list(runtime.runs_dir.iterdir())


def test_setup_permit_is_consumed_once(settings):
    settings.enable_regtest_mutations = True
    settings.require_operator_approval = True
    runtime = Runtime(settings)
    with runtime.operation(mutate=True):
        approve(runtime, "setup")
        consume(runtime, "setup")
        with pytest.raises(SafetyError, match="local operator approval"):
            consume(runtime, "setup")


def test_expired_permit_fails_closed(settings):
    settings.enable_regtest_mutations = True
    settings.require_operator_approval = True
    runtime = Runtime(settings)
    path = runtime.root / "operator-approval.json"
    with runtime.operation(mutate=True):
        approve(runtime, "setup")
        permit = json.loads(path.read_bytes())
        write_json(path, {**permit, "expires_at": 0})
        with pytest.raises(SafetyError, match="local operator approval"):
            consume(runtime, "setup")
    assert not runtime.state_file.exists()

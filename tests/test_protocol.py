import json

import pytest
from mcp import Client, MCPError

from liana_mcp.runtime import Runtime
from liana_mcp.server import create_server


@pytest.mark.anyio
async def test_sdk_protocol_and_default_tools(settings):
    server = create_server(Runtime(settings))
    async with Client(server, mode="2026-07-28") as client:
        tools = await client.list_tools()
        assert [t.name for t in tools.tools] == ["liana_demo_status", "verify_liana_demo"]
        for tool in tools.tools:
            assert tool.annotations.read_only_hint is True
            assert tool.annotations.open_world_hint is False
            assert tool.input_schema["additionalProperties"] is False
            assert tool.output_schema is not None
        result = await client.call_tool("liana_demo_status", {})
        assert result.is_error is False
        assert result.structured_content["status"] == "not_started"
        assert result.structured_content["experimental"] is True
        assert result.structured_content["peer_connections"] is None
        assert str(settings.state_directory) not in json.dumps(result.model_dump())


@pytest.mark.anyio
async def test_mutation_advertisement_requires_operator_setting(settings):
    settings.enable_regtest_mutations = True
    async with Client(create_server(Runtime(settings))) as client:
        tools = (await client.list_tools()).tools
        assert len(tools) == 4
        assert tools[-1].name == "next_liana_demo_step"
        assert tools[-1].annotations.destructive_hint is True
        assert tools[-1].annotations.idempotent_hint is True


@pytest.mark.anyio
@pytest.mark.parametrize("args", [{"seed": "do-not-echo-sentinel"}, [], "text", None])
async def test_unexpected_tool_inputs_fail_without_echo(settings, args):
    server = create_server(Runtime(settings))
    async with Client(server) as client:
        if not isinstance(args, dict):
            # Raw invalid types are tested at the gate: the SDK client refuses them locally.
            from jsonschema import Draft202012Validator

            from liana_mcp.server import InputGate

            gate = InputGate()
            gate.validators["liana_demo_status"] = Draft202012Validator(
                {"type": "object", "properties": {}, "additionalProperties": False}
            )
            from types import SimpleNamespace

            async def unreachable(ctx):
                pytest.fail("Invalid request reached handler")

            with pytest.raises(MCPError):
                await gate(
                    SimpleNamespace(
                        method="tools/call",
                        protocol_version="2026-07-28",
                        params={"name": "liana_demo_status", "arguments": args},
                    ),
                    unreachable,
                )
        else:
            with pytest.raises(MCPError) as error:
                await client.call_tool("liana_demo_status", args)
            assert "do-not-echo-sentinel" not in str(error.value)


@pytest.mark.anyio
async def test_unknown_tool_and_wrong_handle(settings):
    async with Client(create_server(Runtime(settings))) as client:
        with pytest.raises(MCPError):
            await client.call_tool("arbitrary_rpc", {})
        result = await client.call_tool("verify_liana_demo", {"run_id": "a" * 32})
        assert result.is_error is True
        assert str(settings.state_directory) not in json.dumps(result.model_dump())


@pytest.mark.anyio
@pytest.mark.parametrize("step", [True, "1", 0, 5, 1.5])
async def test_step_inputs_are_strict_before_backend_access(settings, step):
    settings.enable_regtest_mutations = True
    async with Client(create_server(Runtime(settings))) as client:
        with pytest.raises(MCPError):
            await client.call_tool(
                "next_liana_demo_step", {"run_id": "a" * 32, "expected_step": step}
            )


@pytest.mark.anyio
async def test_protocol_downgrade_is_rejected(settings):
    def leaves(error):
        if isinstance(error, BaseExceptionGroup):
            return [part for child in error.exceptions for part in leaves(child)]
        return [error]

    failure = None
    try:
        async with Client(create_server(Runtime(settings)), mode="legacy"):
            pytest.fail("Initialization-era client was accepted")
    except (MCPError, BaseExceptionGroup) as error:
        failure = leaves(error)
    assert failure is not None
    assert any(isinstance(error, MCPError) and error.error.code == -32022 for error in failure)
    assert not Runtime(settings).state_file.exists()

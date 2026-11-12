"""Exercise another wallet policy through real current-protocol stdio and consensus."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from liana_mcp.config import Settings
from liana_mcp.runtime import Runtime


@pytest.mark.integration
@pytest.mark.anyio
async def test_configurable_wallet_roundtrip():
    config = os.environ.get("LIANA_MCP_CONFIGURABLE_TEST_CONFIG")
    if not config:
        pytest.skip("Set LIANA_MCP_CONFIGURABLE_TEST_CONFIG to a disposable namespace")
    settings = Settings.load(Path(config))
    assert settings.enable_regtest_mutations and settings.require_operator_approval
    runtime = Runtime(settings)
    assert not runtime.state_file.exists()
    command = [sys.executable, "-m", "liana_mcp.cli", "--config", config]
    params = StdioServerParameters(command=command[0], args=command[1:])

    def approve(request):
        subprocess.run(
            [*command, "--approve-wallet-request", json.dumps(request)],
            check=True,
            capture_output=True,
        )

    try:
        async with Client(params, mode="2026-07-28", read_timeout_seconds=90) as client:
            initial = await client.call_tool("regtest_wallet_status", {})
            assert initial.structured_content["status"] == "not_started"
            setup = {
                "kind": "setup",
                "policy": {
                    "primary_keys": 3,
                    "primary_signatures": 2,
                    "recovery_signer": 2,
                    "recovery_blocks": 4,
                },
            }
            approve(setup)
            different = {**setup, "policy": {**setup["policy"], "recovery_blocks": 5}}
            refused = await client.call_tool("setup_regtest_wallet", {"request": different})
            assert refused.is_error and not runtime.state_file.exists()
            opened = await client.call_tool("setup_regtest_wallet", {"request": setup})
            assert not opened.is_error, opened.content
            status = opened.structured_content
            assert status["policy"] == setup["policy"]
            assert status["network"] == "regtest" and status["peer_connections"] == 0
            run = status["run_id"]
            legacy = await client.call_tool(
                "next_liana_demo_step", {"run_id": run, "expected_step": 1}
            )
            assert legacy.is_error
            legacy_approval = subprocess.run([*command, "--approve-step", "1"], capture_output=True)
            assert legacy_approval.returncode == 2

            def request(revision, action):
                return {
                    "kind": "act",
                    "run_id": run,
                    "expected_revision": revision,
                    "action": action,
                }

            async def act(payload):
                approve(payload)
                result = await client.call_tool("regtest_wallet_action", {"request": payload})
                assert not result.is_error, result.content
                return result.structured_content

            deposit = request(0, {"kind": "deposit", "amount_sats": 23_000})
            unfunded = await client.call_tool("regtest_wallet_action", {"request": deposit})
            assert unfunded.is_error
            funded = await act(deposit)
            assert funded["coins"][0]["recovery_blocks_remaining"] == 3
            assert funded["transaction"]["output_sats"] == 23_000
            replay = await client.call_tool("regtest_wallet_action", {"request": deposit})
            assert replay.structured_content == funded
            recover = {
                "kind": "spend",
                "coin": 0,
                "path": "recovery",
                "signers": [],
                "destination": "test_sink",
            }
            early = request(1, recover)
            approve(early)
            refused = await client.call_tool("regtest_wallet_action", {"request": early})
            assert refused.is_error
            renewed = await act(
                request(
                    1,
                    {
                        "kind": "spend",
                        "coin": 0,
                        "path": "primary",
                        "signers": [1, 3],
                        "destination": "wallet",
                    },
                )
            )
            assert renewed["coins"] == [
                {
                    "coin": 1,
                    "amount_sats": 22_000,
                    "confirmations": 1,
                    "recovery_blocks_remaining": 3,
                }
            ]
            mined = await act(request(2, {"kind": "mine", "blocks": 3}))
            assert mined["coins"][0]["recovery_blocks_remaining"] == 0
            recovered = await act(request(3, {**recover, "coin": 1}))
            assert recovered["transaction"]["verified_in_liana_and_core"] is True
            assert recovered["transaction"]["output_sats"] == 21_000
            assert recovered["transaction"]["fee_sats"] == 1000
            assert recovered["coins"] == []
            assert not {funded["transaction"]["txid"], renewed["transaction"]["txid"]} & {
                recovered["transaction"]["txid"]
            }
    finally:
        if runtime.state_file.exists() and runtime.record().stage == "ready":
            with runtime.operation(mutate=True):
                runtime.stop()

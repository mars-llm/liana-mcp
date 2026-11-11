"""Real subprocess/stdio integration. Never substitute a mock Bitcoin backend."""

import json
import os
import sys
import time
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from liana_mcp.approval import approve
from liana_mcp.config import Settings
from liana_mcp.runtime import Runtime


@pytest.mark.integration
@pytest.mark.anyio
async def test_real_regtest_roundtrip():
    config = os.environ.get("LIANA_MCP_TEST_CONFIG")
    if not config:
        pytest.skip("Set LIANA_MCP_TEST_CONFIG to an explicit private, disposable regtest config")
    settings = Settings.load(Path(config))
    runtime = Runtime(settings)
    assert settings.enable_regtest_mutations
    assert not runtime.state_file.exists(), "Integration test requires a fresh private namespace"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "liana_mcp.cli", "--config", config],
        env={"PATH": "/usr/bin:/bin", "OTEL_SDK_DISABLED": "true"},
    )

    def allow(action):
        if settings.require_operator_approval:
            with runtime.operation(mutate=True):
                approve(runtime, action)

    result_rows = []
    try:
        # Current MCP throughout, with a real server process restart between stages.
        async with Client(params, mode="2026-07-28", read_timeout_seconds=90) as client:
            if settings.require_operator_approval:
                refused = await client.call_tool("setup_liana_demo", {})
                assert refused.is_error and not runtime.state_file.exists()
            allow("setup")
            begin = time.monotonic()
            setup = await client.call_tool("setup_liana_demo", {})
            assert not setup.is_error, setup.content
            run_id = setup.structured_content["run_id"]
            result_rows.append({"operation": "setup", "seconds": time.monotonic() - begin})
            for step in (1, 2):
                allow(str(step))
                begin = time.monotonic()
                result = await client.call_tool(
                    "next_liana_demo_step", {"run_id": run_id, "expected_step": step}
                )
                assert not result.is_error, result.content
                assert result.structured_content["completed_step"] == step
                checks = result.structured_content["checks"]
                assert checks["primary_three"]
                assert checks["primary_two_rejected"]
                assert checks["primary_one_rejected"]
                assert checks["early_rejected"]
                if step == 2:
                    assert checks["old_ready"]
                    assert checks["young_locked"]
                    assert checks["primary_after_topup"]
                result_rows.append(
                    {"operation": f"step_{step}", "seconds": time.monotonic() - begin}
                )
                replay = await client.call_tool(
                    "next_liana_demo_step", {"run_id": run_id, "expected_step": step}
                )
                assert not replay.is_error
                assert replay.structured_content == result.structured_content
        async with Client(params, mode="2026-07-28", read_timeout_seconds=90) as client:
            status = await client.call_tool("liana_demo_status", {})
            assert status.structured_content["run_id"] == run_id
            assert status.structured_content["completed_step"] == 2
            wrong = await client.call_tool(
                "next_liana_demo_step", {"run_id": run_id, "expected_step": 4}
            )
            assert wrong.is_error
            for step in (3, 4):
                allow(str(step))
                begin = time.monotonic()
                result = await client.call_tool(
                    "next_liana_demo_step", {"run_id": run_id, "expected_step": step}
                )
                assert not result.is_error, result.content
                checks = result.structured_content["checks"]
                assert checks["primary_after_topup"]
                assert checks["primary_after_refresh"]
                if step == 3:
                    assert checks["refresh_locked"]
                else:
                    coins = result.structured_content["coins"]
                    assert [coin["amount_sats"] for coin in coins] == [99000]
                    assert coins[0]["blocks_remaining"] == 4
                    assert result.structured_content["recovery_blocks"] == 6
                    payment = result.structured_content["confirmed_recovery_payment"]
                    assert payment == {
                        "wallet_input_sats": 10000,
                        "destination_received_sats": 9000,
                        "miner_fee_sats": 1000,
                    }
                    replay = await client.call_tool(
                        "next_liana_demo_step", {"run_id": run_id, "expected_step": 4}
                    )
                    assert not replay.is_error
                    assert replay.structured_content == result.structured_content
                result_rows.append(
                    {"operation": f"step_{step}", "seconds": time.monotonic() - begin}
                )
            begin = time.monotonic()
            # Wait only for the real wallet daemon to observe the just-mined blocks.
            import anyio

            deadline = time.monotonic() + 10
            while True:
                proof = await client.call_tool("verify_liana_demo", {"run_id": run_id})
                if not proof.is_error or time.monotonic() >= deadline:
                    break
                await anyio.sleep(0.3)
            assert not proof.is_error, proof.content
            assert proof.structured_content["confirmed_transactions_in_liana_and_core"] == 4
            assert proof.structured_content["renewed_unspent_sats"] == 99000
            assert proof.structured_content["wallet_spend_fees_sats"] == {
                "renewal": 1000,
                "recovery": 1000,
            }
            assert proof.structured_content["recovery_destination_sats"] == 9000
            assert proof.structured_content["renewal_primary_signatures"] == 3
            assert proof.structured_content["recovery_signatures"] == 1
            assert proof.structured_content["external_peers"] == 0
            assert proof.structured_content["recovery_blocks"] == 6
            amounts = {row["amount_sats"] for row in proof.structured_content["transactions"]}
            assert amounts == {100000, 10000, 99000, 9000}
            assert [x["fee_sats"] for x in proof.structured_content["transactions"]] == [1000] * 4
            assert all(
                x["liana_and_core_transaction_bytes_equal"]
                for x in proof.structured_content["transactions"]
            )
            result_rows.append({"operation": "verify", "seconds": time.monotonic() - begin})
            serialized = json.dumps(proof.model_dump())
            assert str(runtime.root) not in serialized
            assert "xprv" not in serialized and "seed_hex" not in serialized
        record = runtime.record()
        raw = json.loads((runtime.run_path(record) / "policy-proof.json").read_text())
        assert raw["all_ten_primary_triples_accepted"]
        assert raw["all_ten_primary_pairs_rejected"]
        (runtime.root / "integration-results.json").write_text(
            json.dumps(
                {"operations": result_rows, "verification": proof.structured_content}, indent=2
            )
        )
    finally:
        if runtime.state_file.exists() and runtime.record().stage == "ready":
            with runtime.operation(mutate=True):
                runtime.stop()

"""Run against the installed MCP server inside the headless container."""

import json
import os
import subprocess

import anyio
from mcp import Client, StdioServerParameters

COMMAND = "/usr/local/bin/liana-mcp-regtest"


async def smoke():
    assert os.geteuid() == 10001
    params = StdioServerParameters(command=COMMAND)
    async with Client(params, mode="2026-07-28", read_timeout_seconds=120) as client:
        docs = await client.call_tool("liana_doc_search", {"query": "recovery timelock"})
        assert not docs.is_error and docs.structured_content["matches"]
        assert docs.structured_content["release"] == "16.0"
        status = await client.call_tool("regtest_wallet_status", {})
        assert status.structured_content["status"] == "not_started"

        async def approved(tool, request):
            subprocess.run([COMMAND, "--approve-wallet-request", json.dumps(request)], check=True)
            result = await client.call_tool(tool, {"request": request})
            assert not result.is_error, result.content
            return result.structured_content

        state = await approved(
            "setup_regtest_wallet",
            {
                "kind": "setup",
                "policy": {
                    "primary_keys": 3,
                    "primary_signatures": 2,
                    "recovery_signer": 3,
                    "recovery_blocks": 4,
                },
            },
        )
        assert state["network"] == "regtest" and state["peer_connections"] == 0

        async def act(revision, action):
            return await approved(
                "regtest_wallet_action",
                {
                    "kind": "act",
                    "run_id": state["run_id"],
                    "expected_revision": revision,
                    "action": action,
                },
            )

        deposit = await act(0, {"kind": "deposit", "amount_sats": 25_000})
        assert deposit["transaction"]["verified_in_liana_and_core"]
        mined = await act(1, {"kind": "mine", "blocks": 3})
        assert mined["coins"][0]["recovery_blocks_remaining"] == 0
        recovery = await act(
            2,
            {
                "kind": "spend",
                "coin": 0,
                "path": "recovery",
                "signers": [],
                "destination": "test_sink",
            },
        )
        assert recovery["transaction"]["verified_in_liana_and_core"]
        assert recovery["transaction"]["output_sats"] == 24_000
        print("Offline documentation, wallet setup, deposit and recovery passed.")


if __name__ == "__main__":
    anyio.run(smoke)

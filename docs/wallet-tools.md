# Configurable regtest wallets

Run the server using the [README setup](../README.md#install-locally). Mutation tools for configurable wallets require both `enable_regtest_mutations = true` and `require_operator_approval = true` in the private operator configuration. The read-only status tool is always available.

| Tool | Purpose |
| --- | --- |
| `regtest_wallet_status` | Inspect the active policy, revision, chain height, spendable outputs and latest action’s transaction receipt |
| `setup_regtest_wallet` | Generate and start a wallet with 2–8 synthetic signers, a spending threshold, and a single-signature recovery path after 1–144 blocks per output |
| `regtest_wallet_action` | Deposit test sats, produce blocks, or spend one confirmed test coin |
| `liana_doc_search` | Find cited excerpts from the packaged Liana 16.0 documentation |
| `liana_doc_read` | Read a specific line range from a release document |

The documentation tools work before you start a wallet and require no connection. Try a query such as `recovery timelock`. Use the returned source link to check the original lines.

Signer numbers start at 1. The recovery signer uses a separate derivation from their primary key. The primary path remains available after the delay. The server owns all test keys, both destinations and the local chain.

Each mutation takes a `request` object. Approve the **inner object** in a separate local terminal, using the same config as the client. Run the command yourself and share only the fact that you approved. Keep general shell and file tools disabled in the wallet session so the agent cannot issue its own permit.

```sh
.venv/bin/python -m liana_mcp.cli --config /absolute/path/to/operator.toml \
  --approve-wallet-request '{"kind":"setup","policy":{"primary_keys":3,"primary_signatures":2,"recovery_signer":3,"recovery_blocks":4}}'
```

Call `setup_regtest_wallet` with that object as `request`. Use the returned run ID and revision to prepare later actions. For `regtest_wallet_action`, the inner object has this shape:

```json
{
  "kind": "act",
  "run_id": "<actual run ID>",
  "expected_revision": 0,
  "action": { "kind": "deposit", "amount_sats": 25000 }
}
```

Replace `action` with one of the following. Approve each new request with the same CLI flag before calling it.

- `{"kind":"deposit","amount_sats":25000}` deposits 2,000–10,000,000 test sats from the owned mining reserve.
- `{"kind":"mine","blocks":3}` produces 1–144 local blocks.
- `{"kind":"spend","coin":0,"path":"primary","signers":[1,3],"destination":"wallet"}` spends a single coin with exactly the required signers. `wallet` sends to a fresh output under the same policy and restarts its clock.
- `{"kind":"spend","coin":1,"path":"recovery","signers":[],"destination":"test_sink"}` spends a mature coin through the recovery path. `test_sink` is an address owned by the isolated test runtime. Both destinations are available to either path.

Deposits and spends mine their confirmation block and wait for Liana to show the same confirmed transaction. Test fees are fixed at 1,000 sats. Status reports a coin’s remaining wait separately from the configured delay. Permits expire after five minutes. A retry of the latest completed request returns the same result. A stale revision or interrupted mutation requires checking status before continuing. If the chain and checkpoint disagree, inspect the isolated run locally.

Stop an owned test backend using the same local command and `--stop`. To try another wallet, stop the first run and request a new policy, or choose a separate private namespace. Existing test state remains on disk. Close the optional GUI normally.

For contributors, use `uv run --frozen --offline ruff check .`, `uv run --frozen --offline ruff format --check .` and `uv run --frozen --offline pytest -m 'not integration'`. Set `LIANA_MCP_CONFIGURABLE_TEST_CONFIG` and `LIANA_MCP_TEST_CONFIG` to two separate private, fresh, disposable configurations to run `pytest -m integration` with real local binaries.

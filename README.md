# Liana MCP

Experimental, local-only MCP tools for **isolated Liana regtest wallets**. Intended for workshops, tests and reproducible experiments. This is an independent project, not an official Liana service. Do not use it with real funds.

The server creates its own wallet and native Bitcoin Core backend. It does not attach to your existing wallets, accept private keys from a model, or expose arbitrary wallet RPC calls. Bitcoin Core validates the real regtest transactions; Liana tracks and displays them. No VM is needed.

## Supported experiment

Five test signers: Alice, Bob, Carol, Dave and Eve. Any three can spend immediately. Carol has a separate recovery derivation that becomes available after six blocks **per confirmed output**. The primary path remains available.

1. Receive 100,000 test sats. Test all ten three-key combinations and reject all ten two-key combinations, one key and early recovery.
2. Receive another 10,000 test sats. Show that a deposit does not reset the older output's age.
3. Alice, Bob and Dave renew the first output: 99,000 sats remain after the test fee, with a new age.
4. Carol spends the mature additional output: 9,000 sats reach the test target.
5. Read the four transactions back from Liana and their confirmed Core blocks, compare their bytes and check the resulting UTXO set.

All five software test keys are on one machine. This demonstrates Bitcoin rules, not secure real-world key custody. Transaction construction and test signing use `embit`; this is not yet a general wrapper around Liana's PSBT creation APIs.

## Install locally

Python 3.12+, `uv`, and macOS or Linux with Unix sockets are required. Install and verify Bitcoin Core and `lianad` separately. An optional, already installed Liana GUI can be configured. The MCP server never downloads executables.

```sh
uv sync --locked
```

Copy [examples/operator.example.toml](examples/operator.example.toml) into a **private local configuration**, set the absolute executable paths and SHA-256 pins, and choose a new, short private state directory. Use mode `0600` for the configuration and `0700` for the state directory. Symlink paths and directories accessible to other users are refused. Do not put the config or generated state in Git.

The default is read-only. To make the fixed experiment available, the operator must explicitly set `enable_regtest_mutations = true` in that local file. A model cannot enable it.

```sh
uv run --frozen --offline liana-mcp --config /absolute/path/to/private/operator.toml
```

This runs **stdio only**, with MCP `2026-07-28` required. Older protocol revisions and initialization-era connections are rejected; there is no downgrade fallback. It opens no MCP HTTP endpoint and performs no remote authentication. Logs and test keys stay in the private state directory. It does not provide an OS sandbox: configure your host's filesystem and network restrictions separately. Never forward stdio or tool results to a remote service without the user's informed approval.

For an independent operator gate, set `require_operator_approval = true` as shown in the example. In a separate local terminal, arm setup or exactly the next step before sending the corresponding tool call:

```sh
uv run --frozen --offline liana-mcp --config /absolute/path/to/private/operator.toml --approve-step setup
```

For the four transaction steps, pass `1`, `2`, `3` or `4` instead of `setup`. Approval expires after five minutes and is consumed before the state changes. It is tied to the current run and checkpoint. Replaying an already completed step returns its saved result without using another approval. Existing configurations that omit this setting retain host-side approval.

## Tools

| Tool | Availability | Effect |
| --- | --- | --- |
| `liana_demo_status` | Always | Read the isolated runtime's status, version and completed step |
| `verify_liana_demo` | Always | Read-only comparison of four confirmed transactions and remaining coins |
| `setup_liana_demo` | Operator enables mutations | Create a fresh test wallet or return the current ready run |
| `next_liana_demo_step` | Operator enables mutations | Execute exactly the expected step in that run |

Setup returns a random `run_id` for a new wallet or the existing ID if the current run is ready. To start another wallet with the same configuration, stop the owned backend first. The previous run remains on disk.

Supply the current `run_id` and `expected_step` (1–4) when advancing. Repeating the current step returns its result without creating another transaction; out-of-order requests fail. This supports recovery after a client or server restart without silently advancing twice. Handles identify a run; they are not authentication credentials.

The wallet policy is reported in `recovery_blocks`. Each coin reports its current wait in `blocks_remaining`. After confirmed recovery, `confirmed_recovery_payment` reports the spent input, the amount received and the miner fee separately.

Cancellation stops delivery of the answer. An in-progress step finishes its bounded checkpoint; a broadcast transaction cannot be undone. Read status before continuing. Incomplete setup or a chain changed outside the workflow fails closed. Files are preserved for inspection.

Stop the owned backend locally:

```sh
uv run --frozen --offline liana-mcp --config /absolute/path/to/private/operator.toml --stop
```

Closing the MCP connection leaves the owned regtest running so another client can reconnect. Close an optional GUI normally. The server never deletes a wallet or kills a process based on a saved PID.

## Agent setup

[Connect Hermes Agent](docs/agent-setup.md) for the local profile, operator approvals and ready-to-use prompts.

## Locally Uncensored

For a host accepting only `npx` launchers, the dependency-free local [client launcher](client-launcher/) starts the already prepared Python environment. It does not install another server or resolve packages online:

```text
Command: npx
Arguments: --offline --yes --package "/absolute/path/to/liana-mcp/client-launcher" liana-mcp-local --config "/absolute/path/to/private/operator.toml"
```

Check the full command before allowing it. Keep the host's general shell, file and web tools disabled if this fixed experiment is all you need. Tool annotations describe effects; they do not replace host-side consent or server-side checks.

## Verify

```sh
uv run --frozen --offline ruff check .
uv run --frozen --offline ruff format --check .
uv run --frozen --offline pytest -m 'not integration'
```

The native integration test requires an explicit private config with a **fresh disposable namespace** and mutation consent:

```sh
LIANA_MCP_TEST_CONFIG=/absolute/path/to/private/test.toml uv run --frozen --offline pytest -m integration
```

It runs real stdio subprocesses using MCP `2026-07-28`, reconnects after a process restart, creates and checks real regtest transactions, and stops its backend. Protocol-downgrade attempts are rejected in the security suite. Unit fixtures test malformed inputs and transport handling; they do not substitute for that Bitcoin test. Build dependencies must be cached before using `--offline`.

The client/remote access requirements are defined in [the access contract](docs/access-contract.md). A documented transport is not a client-certification claim.

See [architecture](docs/architecture.md), [compatibility and API coverage](docs/compatibility.md), and [security boundaries](SECURITY.md).

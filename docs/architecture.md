# Architecture

`MCP host → official MCP Python SDK → validated tool contract → private runtime → Liana Unix RPC / Bitcoin Core loopback RPC`

The model chooses a declared tool. It does not choose a command, network, executable, wallet path, RPC method, recipient or fee. Those belong to the fixed local test scenario or operator configuration.

| Module | Responsibility |
| --- | --- |
| `config.py` | Strict operator configuration, private filesystem permissions and executable pins |
| `rpc.py` | Allowlisted, bounded local RPC with response-ID checks and sanitized errors |
| `runtime.py` | Separate owned directories, native process startup, network/policy guards and cross-process locking |
| `scenario.py` | Deterministic experiment stages, synthetic funding, test signatures and actual Core validation |
| `verification.py` | Independent transaction, signature, label and UTXO readback from Core and Liana |
| `server.py` | Official SDK, input/output schemas, effect annotations, input validation and call limiting |
| `cli.py` | Operator entry point and local backend shutdown |

## Protocol and state

MCP `2026-07-28` is mandatory and uses per-request version/capability metadata. A server-side gate rejects older revisions and `initialize` requests before any tool can execute. There is no compatibility fallback. The official SDK owns message parsing and transport; application code does not echo client versions or implement another JSON-RPC dispatcher.

The persisted run is application state, not MCP connection state. Each run has a random 128-bit identifier, private records and fixed policy. A client must present the current identifier to advance it. The `expected_step` argument makes a retry of the current stage idempotent and rejects skipped stages. A filesystem lock serializes calls across server processes. Every live operation checks the network, absence of peers, executable pins, wallet policy and expected chain height.

State writes use private temporary files, `fsync` and atomic replacement. Files remain after stopping. An interrupted operation is not rolled back: if chain height and checkpoint disagree, further automation is refused. A fresh operator-selected namespace is required for a new experiment after investigating an incomplete setup.

## Bitcoin and Liana

Core runs natively with a 16 MiB database cache, 8 MiB mempool cap, one validation worker, no listening peers, no DNS discovery and loopback-only RPC. Its authentication cookie never enters an MCP result. Liana connects to that node through a private config and exposes its normal owner-only Unix socket.

Liana v16 replies can be complete JSON objects without a newline terminator. The RPC client handles fragmented reads, waits for a complete JSON object, checks its ID, and enforces a total deadline and size limit. It validates the live `descriptors.main.multi_desc` against the generated policy.

The experiment uses P2WSH and an `embit` signer outside the model context. The GUI displays actual wallet records. Neither a generated explanation nor a successfully returned MCP call replaces the final chain readback.

## Compatibility policy

SDK and application versions are pinned in `uv.lock`. A dependency update requires current-protocol and downgrade-rejection tests and a real regtest run. A new Liana version or address type needs an explicit compatibility check and the same consensus assertions before it is admitted. Unknown wallet versions are refused. Tests on one platform or protocol do not establish support for untested combinations.

# Security boundaries

This is an experimental regtest service for local tests, education and development. It is not audited wallet infrastructure and is not intended for real funds. It is independent of the Liana maintainers.

## Enforced by the server

- **Current MCP only:** revision `2026-07-28` is required. Initialization-era requests and older revisions are rejected before tool execution. No fallback mode is exposed.

- **Local stdio only:** no MCP HTTP listener, OAuth, remote endpoint, arbitrary URL, proxy forwarding or runtime executable download.
- **Read-only by default:** mutation tools exist only when the operator enables the fixed regtest experiment in a private config. MCP arguments cannot change this setting.
- **Independent operator approval:** when enabled, each new mutation requires an expiring, single-use permit created by the local CLI. The permit is bound to the current run and checkpoint. This mode assumes the host cannot run the operator CLI or write to the private state directory.
- **Separate state:** fresh directories only, private file permissions, random run IDs, symlink refusal, pinned executables and no connection to existing wallets.
- **Checks on every live call:** regtest network, zero peers, expected chain state and the actual wallet descriptor. Unknown Liana versions are refused.
- **Small input surface:** declared schemas, rejected extra arguments, structured output schemas, bounded arguments, a per-process call limit and a cross-process lock. There is no raw RPC passthrough or shell tool.
- **Bounded local RPC:** fixed methods, numeric loopback address or owned Unix socket, response-ID validation, timeouts and response-size limits. Cookies and keys are never returned.
- **Private diagnostics:** native backend logs and checkpoints stay in the private state directory. Tool failures do not echo raw RPC errors, local paths, credentials or tracebacks. No telemetry exporter is configured; the CLI disables OpenTelemetry SDK processing.

The host must show the exact startup command and obtain informed consent before starting the server, enabling tools or sending results to a remote model. Tool annotations are hints, not authorization. A file's content, a wallet label or a tool response cannot authorize further actions or data disclosure.

## Threat model and limits

The design protects against unexpected model arguments, accidental use of another network/profile, duplicated or concurrent calls and unintended exposure in tool results. It does not protect against a compromised administrator, hostile software with the same OS identity, a malicious MCP host, or a tampered Python environment. A hash pin detects changes relative to a trusted pin; it does not prove who built a binary. Verify sources and signatures separately.

The Python process is not an OS sandbox. A host-level sandbox should restrict it to its config, pinned runtimes, private state, loopback RPC and owned Unix sockets. The project does not require a VM. No network-disconnection claim follows merely from selecting a local model or reaching zero Bitcoin peers.

The test wallet stores all five disposable keys locally. Do not fund its addresses outside regtest or reuse its keys. The state directory contains secrets and wallet history even though MCP results omit them. Never commit or upload it. The server deliberately provides no deletion tool.

Cancellation cannot undo a broadcast transaction. A running step finishes its bounded checkpoint; inspect status before retrying. Closing stdio leaves the backend available for reconnection. Use the local CLI to stop it. Incomplete setup and unexpected chain changes require local inspection rather than automatic reset or repair.

## Reporting an issue

Share a minimal reproduction using a newly created regtest. Exclude seeds, private keys, cookies, descriptors, identifying paths and raw logs. Arrange a private reporting destination with the repository owner before sharing sensitive details. This repository does not automatically upload diagnostics.

Reference: [MCP security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices).

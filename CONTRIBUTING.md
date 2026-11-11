# Contributing

Keep protocol, local RPC, runtime supervision and experiment logic separate. Use the official MCP SDK; do not add a second protocol implementation. Changes to tool names, schemas, defaults or supported versions are compatibility changes.

Run the locked formatter, linter and unit/protocol suite. Changes affecting wallet setup, transactions, retries, recovery or runtime state also require the real integration test. Keep the original failed-run evidence locally; do not turn a fixture, model answer or simulated backend into a Bitcoin success claim.

No secrets, local configs, runtime directories, raw logs or identifying screenshots belong in commits. Prepare a clean diff and explain the behavior, checks performed and remaining limits. General PSBT support, new networks, downloads, remote transport and signing custody require a separate design and security review before implementation.

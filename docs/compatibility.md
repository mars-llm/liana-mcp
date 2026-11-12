# Compatibility and API coverage

## Baseline

| Component | Contract |
| --- | --- |
| MCP | `2026-07-28` only; older versions rejected |
| Python SDK | `mcp==2.3.0` |
| Python | 3.12 or newer |
| Native and container backend | Bitcoin Core 32.1, isolated regtest |
| Wallet version gate | Liana `16.0` final only |
| Wallet policies | P2WSH, 2–8 primary keys, a user-selected threshold, and one recovery signer after 1–144 blocks |

The native integration suite covers the workshop workflow and independent actions on a configurable wallet. The [Docker image](container.md) packages both daemons for Linux x86-64. The GUI is available in the native setup. Windows is outside the native Unix-socket implementation.

The read-only documentation tools include usage, recovery, signing devices, labels, regtest examples and the API reference from [Liana 16.0](https://github.com/wizardsardine/liana/tree/ad203b7fbefae6f2b5b36f25db41ff0e0e2acd13/doc).

## If discovery fails in your client

Check that the client launches the configured executable with local stdio and includes `2026-07-28` metadata in its MCP requests. If it sends `initialize` or uses an older protocol, update the client's MCP SDK and the code that creates its stdio connection to use the current stateless client. Then test `tools/list` and `regtest_wallet_status` before enabling writes. For LU 3.0.9 the relevant client file is [`src/api/mcp/external-client.ts`](https://github.com/PurpleDoubleD/locally-uncensored/blob/v3.0.9/src/api/mcp/external-client.ts). For a separate local profile, see the [Hermes configuration](agent-setup.md). Keep the protocol gate and approval checks in the server.

## Liana feature boundaries

| Liana capability | Current use / exposure |
| --- | --- |
| `getinfo` | Internal network, version, policy and synchronization checks; sanitized MCP status |
| `listtransactions`, `getlabels` | Readback of the known experiment's transactions and labels |
| `updatelabels` | Fixed experiment labels only; no arbitrary user input |
| Wallet setup | Fresh local test config and synthetic signers; no import of existing wallets |
| Receive, renew, recovery | Configurable, independently approved deposits, blocks and single-output spends constructed and signed outside the model |
| Coin browsing | Own generated wallet outputs and their current recovery wait |
| `createspend`, `createrecovery`, `updatespend`, `listspendtxs` | Not exposed as general PSBT operations |
| `broadcastspend`, `delspendtx`, `rbfpsbt`, `checkrbf` | Not exposed |
| Derivation-index updates, rescans and BIP329 export | Not exposed |
| Taproot, arbitrary descriptors, hardware signers, encrypted backup import/export | Not implemented in this experiment |
| Liana Connect / Business, remote nodes and accounts | Not supported |
| Mainnet, testnet, signet or real-funds signing | Refused / outside this project's current scope |

A general Liana integration needs separate authorization and validation for each operation. Draft creation, inspection, signing and broadcasting must remain distinct. The fixed test signer must never become a real-funds key service.

## Upstream check

On 5 November 2026, the complete `wizardsardine/liana` master tree at `dabad663dd634cdb87166f6333f5da525898606e`, repository text, and public issue/PR searches for “MCP” and “Model Context Protocol” showed no Bitcoin Liana MCP implementation. A repository search also returned an unrelated single-cell biology project with the same Liana name. This bounded search is not proof that no independent integration exists elsewhere.

References:

- [Liana API](https://github.com/wizardsardine/liana/blob/dabad663dd634cdb87166f6333f5da525898606e/doc/API.md)
- [Liana v16.0](https://github.com/wizardsardine/liana/releases/tag/v16.0)
- [MCP versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning)
- [MCP stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)
- [MCP tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [Official Python SDK v2.3.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)

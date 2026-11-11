# Compatibility and API coverage

## Baseline

| Component | Contract |
| --- | --- |
| MCP | `2026-07-28` only; older versions rejected |
| Python SDK | `mcp==2.3.0` |
| Python | 3.12 or newer |
| Native backend | Bitcoin Core 31.1, isolated regtest |
| Wallet version gate | Liana `16.0` final only |
| Experiment policy | P2WSH, 3 of 5, Carol on a separate derivation after 6 blocks |

The current native integration was exercised on macOS ARM64 with `lianad` 16.0 final and Bitcoin Core 31.1. It uses current-protocol stdio throughout and restarts the server process between stages 2 and 3. The v16.0 API was also checked against upstream documentation/source. This is not a Linux, Windows, Taproot, hardware-wallet or physical-offline certification. Windows is not supported by this Unix-socket implementation.

## Liana feature boundaries

| Liana capability | Current use / exposure |
| --- | --- |
| `getinfo` | Internal network, version, policy and synchronization checks; sanitized MCP status |
| `listtransactions`, `getlabels` | Readback of the known experiment's transactions and labels |
| `updatelabels` | Fixed experiment labels only; no arbitrary user input |
| Wallet setup | Fresh local test config and synthetic signers; no import of existing wallets |
| Receive, renew, recovery | Fixed real regtest transactions constructed and signed outside the model |
| General address or coin browsing | Not exposed |
| `createspend`, `createrecovery`, `updatespend`, `listspendtxs` | Not exposed as general PSBT operations |
| `broadcastspend`, `delspendtx`, `rbfpsbt`, `checkrbf` | Not exposed |
| Derivation-index updates, rescans and BIP329 export | Not exposed |
| Taproot, arbitrary policies, hardware signers, encrypted backup import/export | Not implemented in this experiment |
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

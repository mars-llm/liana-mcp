# Client access contract

The server's minimum protocol is **MCP 2026-07-28**. Clients must implement it. An older client's failure does not authorize a protocol downgrade, weaker authentication or broader tools. Client names are not authentication and must not be spoofed to bypass another service's policy.

## Local process access

A local client launches the pinned, prepared server over stdio. There is no network listener, browser-accessible bridge or shared bearer secret. The operator controls the private config and state namespace; the host obtains consent for the exact command and exposed tools. The Python environment and executables must be trusted and integrity checked. Filesystem/network confinement is a separate host requirement, not a promise made by an MCP tool annotation.

## Remote access requirements

Remote access is **not implemented or enabled** in this initial release. ChatGPT app/plugin access requires a reachable Streamable HTTP endpoint rather than a local stdio process. The following is the required contract for that separate transport implementation, not a claim that the CLI already provides it:

- HTTPS with a fixed canonical resource URL, current TLS configuration and validated server certificates. No anonymous public tunnel or unauthenticated localhost-to-Internet forwarding.
- OAuth 2.1 authorization-code flow with PKCE S256, protected-resource metadata (RFC 9728), authorization-server metadata (RFC 8414), and an explicitly approved identity provider/client-registration policy. Use a maintained authorization server rather than implementing password storage or an ad hoc token issuer here.
- Verify token signature, pinned issuer, resource audience, expiry and authorized scopes on every request. Restrict signing algorithms and key sources. Never accept a client-chosen issuer, arbitrary discovery URL or a token intended for another service. Never forward access tokens to Liana or Core.
- Separate read, setup and advance privileges. A read grant must not expose mutation tools or permit their invocation by name. Per-call authorization is required in addition to filtered discovery and explicit local regtest consent.
- Bind each run to its authorized principal and private namespace; an opaque run ID is not a capability. Prevent cross-principal reads, retries and state reuse.
- Exact host/origin policy, bounded bodies and deadlines, per-principal rate limits, serialized mutations and safe cancellation. No cookies as a substitute for MCP bearer authorization, no generic CORS allowance and no trust in forwarded headers from unknown proxies.
- Minimize identity claims and scopes; no email/profile collection for this experiment. Redact tokens and identifying payloads from diagnostics. Record only the minimal local audit events needed to investigate actions.
- The same current-protocol gate, regtest restriction, private-key isolation and real-consensus tests apply to both transports. No real-funds mode.

Before deployment: configure and review the exact domain, TLS termination, identity provider, allowed clients, disclosures and access scopes. Test unauthenticated, expired, wrong-issuer, wrong-audience, wrong-scope, replay, downgrade, cross-user and cancellation cases. Remote access stays disabled until those checks and human review pass.

## Client matrix

This table distinguishes documentation from actual acceptance. A product's support for a transport does not establish support for this server's minimum protocol or all its security requirements.

| Client | Documented integration route | This project’s acceptance |
| --- | --- | --- |
| Official Python SDK 2.3.0 client | Current-protocol stdio | Tested with real setup, four transactions, retries, restart and chain readback |
| Codex CLI/app | stdio or Streamable HTTP; OAuth for remote access | Product documentation checked; no end-to-end product acceptance claimed |
| ChatGPT apps/plugins | Reachable HTTPS Streamable HTTP; OAuth for authenticated service | Authenticated remote transport and product acceptance outstanding |
| Claude Code | stdio or HTTP; OAuth for remote access | Product documentation checked; no end-to-end product acceptance claimed |
| Pi Coding Agent | Built-in MCP configuration and extension registration; stdio or HTTP/OAuth | Product documentation checked; no end-to-end product acceptance claimed |
| Hermes Agent | stdio or remote HTTP/OAuth, tool filtering | Product documentation checked; no end-to-end product acceptance claimed |
| Locally Uncensored 3.0.9 | Local stdio launcher; source sends initialize with 2024-11-05 | Incompatible with the required protocol; needs a client update, no fallback |

Each accepted product/version needs its own recorded run: discovery, strict schemas, read-only scope, rejected unauthorized operations, setup/advance retry behavior, cancellation, restart, errors and result rendering. A protocol SDK test alone is not that acceptance.

Sources checked on 5 November 2026:

- [Official OpenAI Docs: Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Official OpenAI Docs: MCP server](https://developers.openai.com/plugins/build/mcp-server)
- [Official OpenAI Docs: Authentication](https://developers.openai.com/plugins/build/auth)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Pi MCP documentation](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/mcp.md)
- [Hermes MCP documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
- [LU 3.0.9 external client](https://github.com/PurpleDoubleD/locally-uncensored/blob/v3.0.9/src/api/mcp/external-client.ts)

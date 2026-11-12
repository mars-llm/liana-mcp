# Liana MCP

<img src="assets/liana-mcp.png" width="420" alt="Liana MCP wordmark">

Liana MCP lets a local AI agent help you plan and test a Bitcoin wallet with [Liana](https://lianawallet.com/) and Bitcoin Core. Choose a spending threshold and a recovery delay, then try deposits, mine blocks and test either spending path with real regtest transactions. The server uses disposable keys and an isolated chain. This is an independent project for testing and education. Use it with test coins only.

## Install locally

You need **macOS or Linux**, Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), [Bitcoin Core 31.1](https://bitcoincore.org/en/download/), [Liana 16.0](https://github.com/wizardsardine/liana/releases/tag/v16.0) with `lianad`, and a local agent that supports **MCP 2026-07-28 over stdio**. Install the Liana desktop app too if you want to see the wallet and transactions. Bring your own agent and local model.

Paste this into your local agent. The agent needs local shell and file access for setup. Use a separate profile with only the Liana MCP tools for the wallet exercise.

```text
Help me set up an isolated Liana regtest wallet using
https://github.com/mars-llm/liana-mcp and my existing local agent.

1. Check my OS and local tools. Find Python 3.12+, uv, Bitcoin Core 31.1,
   lianad 16.0 and the optional Liana desktop executable. Tell me what is
   missing and use official sources for any approved installs. Verify
   binary provenance and release signatures or checksums before pinning
   the SHA-256 of each installed executable. Ask before downloads or
   installation. Use no administrator access.

2. Clone the repository into a new directory, or use a checkout I choose.
   Run uv sync --locked there. Outside Git, create a new short private
   state directory (0700, absolute path at most 40 bytes) and an
   operator.toml (0600) from
   examples/operator.example.toml. Use absolute, resolved binary paths and
   the verified SHA-256 pins. Include the GUI pin if I want the app.
   Set enable_regtest_mutations and require_operator_approval to true.

3. Show the exact command and arguments, then register Liana MCP in a
   separate local profile after I approve:
   command: <checkout>/.venv/bin/python
   args: [-m, liana_mcp.cli, --config, <absolute path to operator.toml>]
   Use local stdio with MCP 2026-07-28. If registration needs a reload,
   explain how. If discovery fails, check docs/compatibility.md and point
   me to my client's stdio transport and MCP SDK. Keep the protocol gate
   and approvals. Offer the Hermes guide if my client is incompatible.

4. Call regtest_wallet_status. Confirm it says regtest and not_started
   before proposing a wallet. Ask how many signers I want, how many must
   sign together, which signer holds the separate recovery key and how
   many blocks each output must wait. Suggest 2 of 3, signer 3 and four
   blocks if I want a simple example. Explain the two spending paths.

5. Show the exact request object for setup_regtest_wallet. Give me a
   terminal command using the same executable and arguments plus
   --approve-wallet-request '<exact request object as JSON>'.
   Wait for me to run it. Then call the tool with that object under
   "request". Read the actual policy and peer count back and show me
   Liana if the GUI was configured. Wait for my next question.

For each later deposit, block-production or spend request, use the
current run ID and revision, show the exact proposed request and wait for
my separate local approval. Use only the registered Liana MCP tools for
the exercise. Keep keys, seeds and private state out of the chat and never
attach to an existing wallet or a public Bitcoin network.
```

Once the wallet is running, try asking **“Deposit 25,000 test sats. How long until this coin can be recovered?”** or **“Can signers 1 and 3 refresh it? What changes about the new coin’s waiting period?”** The agent can also explain policies without calling tools. When it does send a test transaction, the service checks its confirmed bytes in both Bitcoin Core and Liana.

See [tool requests and approval examples](docs/wallet-tools.md), [client compatibility and where to update an older client](docs/compatibility.md), and [Hermes as an optional client](docs/agent-setup.md). The [3-of-5 workshop exercise](docs/agent-setup.md#english-prompts) still works as a guided example. For backend behavior and security limits, see [architecture](docs/architecture.md) and [security](SECURITY.md).

## License

[MIT](LICENSE)

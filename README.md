# Liana MCP

<img src="assets/liana-mcp.png" width="420" alt="Liana MCP wordmark">

Liana MCP lets a local AI agent help you plan and test a Bitcoin wallet with [Liana](https://lianawallet.com/) and Bitcoin Core. Choose a spending threshold and a recovery delay, then try deposits, mine blocks and test either spending path with real regtest transactions. The server uses disposable keys and an isolated chain. This is an independent project for testing and education. Use it with test coins only.

## Install locally

For a native install on macOS or Linux, use [Python 3.12+](https://www.python.org/downloads/), [uv](https://github.com/astral-sh/uv/releases/tag/0.13.7), `lianad` from the [Liana 16.0 release](https://github.com/wizardsardine/liana/releases/tag/v16.0) and `bitcoind` from [Bitcoin Core 32.1](https://bitcoincore.org/bin/bitcoin-core-32.1/). The Liana desktop app is optional. Connect a local agent that supports [MCP 2026-07-28 over stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio).

Liana 16.0 can download and manage Bitcoin Core 31.1 during desktop setup. Liana MCP starts its own isolated regtest process with a verified `bitcoind` executable. Reuse a verified 32.1 binary you already have, or extract just `bitcoind` from the [official archive](https://bitcoincore.org/bin/bitcoin-core-32.1/) after checking its [release checksums](https://bitcoincore.org/bin/bitcoin-core-32.1/SHA256SUMS). [Liana's managed Core version](https://github.com/wizardsardine/liana/blob/ad203b7fbefae6f2b5b36f25db41ff0e0e2acd13/liana-gui/src/node/bitcoind.rs#L30-L36)

[The Dockerfile](Dockerfile) packages both daemons and the Python environment. Use the [container instructions](docs/container.md) for a headless Linux x86-64 build with isolated runtime networking.

Paste this into your local agent. The agent needs local shell and file access for setup. Use a separate profile with only the Liana MCP tools for the wallet exercise.

```text
Help me set up an isolated Liana regtest wallet using
https://github.com/mars-llm/liana-mcp and my existing local agent.

1. Ask whether I want a native or Docker install. Clone this repository
   into a new directory or use a checkout I choose. Check the required
   tools and use the official release links under Install locally.
   Ask before downloads or installation. Use no administrator access.

2. For a native install, find Python 3.12+, uv, lianad 16.0 and bitcoind
   32.1. Reuse a verified 32.1 executable, or verify the official
   archive and extract bitcoind. When checking bitcoind --version,
   pass -datadir=<fresh temporary directory>. Liana 16.0's desktop
   setup manages Core 31.1. Keep my existing node and its data separate.
   Run uv sync --locked. Outside Git, make an operator.toml (0600)
   from examples/operator.example.toml. Use a fresh private state
   directory (0700, at most 40 bytes in its absolute path), resolved
   executable paths and verified SHA-256 pins. Include the GUI pin if
   requested. Set enable_regtest_mutations and require_operator_approval
   to true. Use this MCP command and arguments:
   <checkout>/.venv/bin/python -m liana_mcp.cli --config <operator.toml>

   For Docker, follow docs/container.md to build and start the named
   container with --network none. Both daemons come from the image.
   Use this MCP command and arguments:
   docker exec -i liana-mcp-regtest /usr/local/bin/liana-mcp-regtest

3. Show the exact command and arguments, then register Liana MCP in a
   separate local profile after I approve.
   Use local stdio with MCP 2026-07-28. If registration needs a reload,
   explain how. If discovery fails, check docs/compatibility.md and point
   me to my client's stdio transport and MCP SDK. Keep the protocol gate
   and approvals. Offer the Hermes guide if my client is incompatible.

4. Call regtest_wallet_status. Confirm it says regtest and not_started
   before proposing a wallet. Ask how many signers I want, how many must
   sign together, which signer holds the separate recovery key and how
   many blocks each output must wait. Suggest 2 of 3, signer 3 and four
   blocks if I want a simple example. Explain the two spending paths.

5. Show the exact request object for setup_regtest_wallet. Give me the
   terminal command with --approve-wallet-request '<exact request JSON>'
   appended. In Docker, use docker exec without -i for this command.
   Wait for me to run it. Then call the tool with that object under
   "request". Read the actual policy and peer count back and show me
   Liana if the GUI was configured. Wait for my next question.

For each later deposit, block-production or spend request, use the
current run ID and revision, show the exact proposed request and wait for
my separate local approval. Use only the registered Liana MCP tools for
the exercise. Keep keys, seeds and private state out of the chat and never
attach to an existing wallet or a public Bitcoin network.

When I ask how Liana works, search the bundled Liana 16.0 docs using
liana_doc_search with English keywords. Use liana_doc_read if you
need more context and cite the returned upstream links. Use live tool
results for questions about the state of my regtest wallet.
```

Once the wallet is running, try asking **“Deposit 25,000 test sats. How long until this coin can be recovered?”** or **“Can signers 1 and 3 refresh it? What changes about the new coin’s waiting period?”** The agent can also explain policies without calling tools. When it does send a test transaction, the service checks its confirmed bytes in both Bitcoin Core and Liana.

See [tool requests and approval examples](docs/wallet-tools.md), [client compatibility and where to update an older client](docs/compatibility.md), and [Hermes as an optional client](docs/agent-setup.md). The [3-of-5 workshop exercise](docs/agent-setup.md#english-prompts) still works as a guided example. For backend behavior and security limits, see [architecture](docs/architecture.md) and [security](SECURITY.md).

## License

[MIT](LICENSE). The packaged Liana 16.0 documentation retains its upstream [BSD 3-Clause license](src/liana_mcp/upstream/liana-16.0/LICENCE).

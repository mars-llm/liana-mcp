# Liana MCP with Hermes Agent

Hermes is one option for connecting a local model. Use a separate local Hermes profile and a model served on your computer.

1. Use the [README setup prompt](../README.md#install-locally) to prepare the private operator config. For the configurable tools, enable both mutation consent and independent operator approval.
2. Select a local model with tool calling. Use a Hermes runtime with MCP SDK 2.3.0 and stateless discovery. Hermes may require an actual context window of at least 64,000 tokens, depending on the local provider. Configure the model endpoint on loopback and apply your local network restrictions.
3. Add the following entry to the Hermes profile's `config.yaml`. Replace both paths with absolute paths. Enable only the `mcp-liana` toolset for this exercise.

```yaml
mcp_servers:
  liana:
    command: /absolute/path/to/liana-mcp/.venv/bin/python
    args: [-m, liana_mcp.cli, --config, /absolute/path/to/private/operator.toml]
    protocol: stateless
    trust: untrusted
    tools:
      include: [regtest_wallet_status, setup_regtest_wallet, regtest_wallet_action, liana_doc_search, liana_doc_read]
      prompts: false
      resources: false
    sampling:
      enabled: false
    elicitation:
      enabled: false
```

For a configurable wallet, continue with the README prompt and [wallet actions](wallet-tools.md). To run the workshop exercise below, change the include list to `[liana_demo_status, setup_liana_demo, next_liana_demo_step, verify_liana_demo]` and use a fresh namespace.

## English prompts

Start with these agent instructions:

> Use only the Liana MCP tools for this regtest exercise. Read the status first. Perform at most the explicitly requested step per message. Use the run ID from the tool result. Never ask for a seed or a private key. Report errors and incomplete results, then wait. Derive amounts, delays and confirmations from tool results.

Check the network before enabling any write operations:

> Which Bitcoin network is Liana MCP configured for? Read the status and tell me if a test wallet is already running.

A fresh profile reports `network: regtest` and `status: not_started`. Check the actual tool result. In the operator config, set `enable_regtest_mutations = true` and `require_operator_approval = true`. Reconnect Hermes and keep its tool confirmation enabled.

Approve setup in a separate terminal from the Liana MCP checkout:

```sh
uv run --frozen --offline liana-mcp --config /absolute/path/to/private/operator.toml --approve-step setup
```

> Set up the 3-of-5 test wallet on regtest. Read its status back and wait for my next message.

Run the same local command with `--approve-step 1`, `2`, `3` or `4` for the corresponding prompt. Send one message at a time and confirm each tool call in Hermes:

1. Make the first test deposit. Which signature combinations did Bitcoin Core check? Wait after that.
2. Make the second test deposit. Which output is already available through the recovery path and which is still locked? Wait after that.
3. Refresh the first deposit using the shared spending path. What waiting period does the wallet policy specify for each new output? How many blocks does the refreshed output still have to wait? State the rule and the remaining wait separately.
4. Spend the mature second output with Carol’s recovery key. How much arrived and what was the fee? Wait after that.

Finally check the confirmed transactions:

> Compare the four confirmed regtest transactions in Liana and Bitcoin Core. What has been verified and what remains open?

Use the actual tool results and the wallet view to verify the answers. The mainnet wallet and its signing devices stay outside this test setup.

If a step fails, read status and inspect Liana before retrying. A tool error can follow a confirmed transaction. Stop the owned backend with the same local command and `--stop`.

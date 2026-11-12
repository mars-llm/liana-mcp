# Run Liana MCP in Docker

Install [Docker Engine](https://docs.docker.com/engine/install/) or [Docker Desktop](https://docs.docker.com/desktop/) and use a local agent with [MCP 2026-07-28 stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio).

The Dockerfile packages [Liana 16.0](https://github.com/wizardsardine/liana/releases/tag/v16.0), [Bitcoin Core 32.1](https://bitcoincore.org/bin/bitcoin-core-32.1/), Python and the locked MCP dependencies. It verifies the upstream archive hashes before extraction. Build for Linux x86-64, the platform for which Liana publishes a Linux release binary. On an Arm host the container engine needs x86-64 emulation. The container runs headless.

From the repository root:

```sh
docker build --platform linux/amd64 --tag liana-mcp:local .
docker run --platform linux/amd64 -d --name liana-mcp-regtest \
  --init --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,nodev \
  --mount type=volume,src=liana-mcp-regtest,dst=/data \
  --entrypoint /bin/sleep liana-mcp:local infinity
```

Set the agent's MCP command to `docker` with these arguments:

```text
exec -i liana-mcp-regtest /usr/local/bin/liana-mcp-regtest
```

The build downloads public dependencies. The runtime uses the named volume for private regtest state and the container's own loopback for RPC. Use `-i` without allocating a terminal so stdio carries MCP messages unchanged. Connect one approved local profile at a time.

Use the inner request JSON described in [wallet actions](wallet-tools.md) when approving an operation from your terminal:

```sh
docker exec liana-mcp-regtest /usr/local/bin/liana-mcp-regtest \
  --approve-wallet-request '<exact request object as JSON>'
```

To stop the test backend and then the container:

```sh
docker exec liana-mcp-regtest /usr/local/bin/liana-mcp-regtest --stop
docker stop liana-mcp-regtest
```

If the wallet was never started, use `docker stop` directly. Start it again with `docker start liana-mcp-regtest` and reconnect the client. The wallet files remain in the volume. After stopping the backend, request a new setup to create a fresh run.

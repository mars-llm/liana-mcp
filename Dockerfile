FROM docker.io/library/python:3.12-slim-bookworm AS build

RUN test "$(dpkg --print-architecture)" = amd64

ADD https://bitcoincore.org/bin/bitcoin-core-32.1/bitcoin-32.1-x86_64-linux-gnu.tar.gz /tmp/core.tar.gz
ADD https://github.com/wizardsardine/liana/releases/download/v16.0/liana-16.0-x86_64-linux-gnu.tar.gz /tmp/liana.tar.gz
ADD https://github.com/astral-sh/uv/releases/download/0.13.7/uv-x86_64-unknown-linux-gnu.tar.gz /tmp/uv.tar.gz

RUN printf '%s  %s\n' \
        61545c17c3120fb7412f896d248b11993af04ec8817aad3649c55b2afb044963 /tmp/core.tar.gz \
        5d89975a5513cb5d008382fe012e8591ab31824d480f8701ffe460c42a861c18 /tmp/liana.tar.gz \
        c5221ff41b7892bfc223543883600125f6a47fe845093e0f5bdff4f359196d83 /tmp/uv.tar.gz \
    | sha256sum -c - \
    && mkdir /release-bin \
    && tar -xOzf /tmp/core.tar.gz bitcoin-32.1/bin/bitcoind > /release-bin/bitcoind \
    && tar -xOzf /tmp/liana.tar.gz liana-16.0-x86_64-linux-gnu/lianad > /release-bin/lianad \
    && tar -xOzf /tmp/uv.tar.gz uv-x86_64-unknown-linux-gnu/uv > /usr/local/bin/uv \
    && chmod 0755 /release-bin/bitcoind /release-bin/lianad /usr/local/bin/uv

WORKDIR /build
COPY pyproject.toml uv.lock LICENSE ./
COPY src ./src
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN uv sync --locked --no-dev --no-editable

FROM docker.io/library/python:3.12-slim-bookworm

COPY --from=build /release-bin/ /usr/local/bin/
COPY --from=build /opt/venv /opt/venv
COPY LICENSE /usr/share/doc/liana-mcp/LICENSE

RUN groupadd --gid 10001 liana-mcp \
    && useradd --uid 10001 --gid 10001 --no-create-home liana-mcp \
    && install -d -m 0700 -o 10001 -g 10001 /data/regtest \
    && install -d /opt/liana-mcp \
    && { printf '%s\n' 'state_directory = "/data/regtest"' \
           'enable_regtest_mutations = true' 'require_operator_approval = true'; \
         for component in core lianad; do \
           binary="/usr/local/bin/$component"; \
           if [ "$component" = core ]; then binary=/usr/local/bin/bitcoind; fi; \
           digest="$(sha256sum "$binary" | cut -d ' ' -f 1)"; \
           printf '\n[%s]\npath = "%s"\nsha256 = "%s"\n' "$component" "$binary" "$digest"; \
         done; \
       } > /opt/liana-mcp/operator.toml \
    && chown 10001:10001 /opt/liana-mcp/operator.toml \
    && chmod 0600 /opt/liana-mcp/operator.toml \
    && printf '%s\n' '#!/bin/sh' \
       'exec /opt/venv/bin/python -m liana_mcp.cli --config /opt/liana-mcp/operator.toml "$@"' \
       > /usr/local/bin/liana-mcp-regtest \
    && chmod 0755 /usr/local/bin/liana-mcp-regtest

ENV PYTHONDONTWRITEBYTECODE=1 OTEL_SDK_DISABLED=true
USER 10001:10001
ENTRYPOINT ["/usr/local/bin/liana-mcp-regtest"]

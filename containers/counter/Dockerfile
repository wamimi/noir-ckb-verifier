# Fixed public counter preview: pinned Linux toolchain for local, no-wallet runs.
#
# Builds an Ubuntu 24.04 image (linux/amd64 or linux/arm64, matching the Docker
# host) with Rust 1.95.0/1.94.1, clang-18, Node/npm + snarkjs 0.7.5, the pinned
# Noir-Groth16 backend revision and verified CKB/ckb-cli/Nargo executables.
# Public-network signing never happens inside this image.
#
# Build from the repository root (see docs/owned-counter-container.md):
#   docker build -f containers/counter/Dockerfile -t noir-ckb-counter .
ARG BASE=ubuntu:24.04
FROM ${BASE}

ARG DEBIAN_FRONTEND=noninteractive
ARG RUSTUP_VERSION=1.28.2
ARG BACKEND_REPO=https://github.com/wamimi/Noir-Groth16
ARG BACKEND_REV=828025f3a0090e2934940956c0f5dc8093eb5532

RUN apt-get update \
 && apt-get install --yes --no-install-recommends \
      ca-certificates curl git python3 build-essential pkg-config clang-18 lld-18 nodejs npm \
 && rm -rf /var/lib/apt/lists/*

# Shared tool homes stay writable so `docker run --user "$(id -u):$(id -g)"` works on Linux hosts.
ENV HOME=/home/counter \
    RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    npm_config_cache=/opt/npm-cache \
    PATH=/opt/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    COUNTER_BACKEND=/opt/Noir-Groth16 \
    PYTHONDONTWRITEBYTECODE=1

# rustup-init from the versioned archive, checked against its published SHA-256 file.
RUN set -eux; \
    case "$(uname -m)" in x86_64) triple=x86_64-unknown-linux-gnu ;; aarch64) triple=aarch64-unknown-linux-gnu ;; \
      *) echo "unsupported architecture $(uname -m)"; exit 1 ;; esac; \
    base="https://static.rust-lang.org/rustup/archive/${RUSTUP_VERSION}/${triple}"; \
    curl --proto '=https' --tlsv1.2 -fsSLo /tmp/rustup-init "$base/rustup-init"; \
    curl --proto '=https' --tlsv1.2 -fsSLo /tmp/rustup-init.sha256 "$base/rustup-init.sha256"; \
    echo "$(cut -d' ' -f1 /tmp/rustup-init.sha256)  /tmp/rustup-init" | sha256sum -c -; \
    chmod +x /tmp/rustup-init; \
    /tmp/rustup-init -y --no-modify-path --profile minimal --default-toolchain none; \
    rm /tmp/rustup-init /tmp/rustup-init.sha256; \
    rustup toolchain install 1.95.0 --profile minimal; \
    rustup toolchain install 1.94.1 --profile minimal --target riscv64imac-unknown-none-elf

RUN git clone --quiet "$BACKEND_REPO" /opt/Noir-Groth16 \
 && git -C /opt/Noir-Groth16 checkout --quiet --detach "$BACKEND_REV" \
 && test "$(git -C /opt/Noir-Groth16 rev-parse HEAD)" = "$BACKEND_REV"

# .dockerignore excludes target/, .local/ and local key material.
COPY . /opt/noir-ckb-verifier
WORKDIR /opt/noir-ckb-verifier

RUN python3 -B scripts/fetch-counter-tools.py --yes --out /opt/noir-ckb-verifier/target/counter-tools \
 && cargo +1.95.0 fetch --locked --manifest-path Cargo.toml \
 && cargo +1.94.1 fetch --locked --manifest-path contracts/Cargo.toml \
 && cargo +1.95.0 fetch --locked --manifest-path /opt/Noir-Groth16/Cargo.toml \
 && npm exec --yes --package=snarkjs@0.7.5 -- node -e 'process.exit(0)' \
 && mkdir -p /home/counter target/runs \
 && chmod -R a+rX /opt/rustup /opt/Noir-Groth16 /opt/noir-ckb-verifier \
 && chmod -R a+rwX /opt/cargo /opt/npm-cache /home/counter target/runs

ENTRYPOINT ["python3", "-B", "scripts/start-counter.py"]
CMD ["doctor"]

#!/usr/bin/env bash
# R4 spike: witness solving (backend compiled to wasm32) and Groth16 proving (snarkjs) in a
# browser. Builds everything, then serves a page that measures itself.
#
#   BACKEND=/path/to/Noir-Groth16 NARGO=/path/to/nargo SNARKJS=/path/to/node_modules/.bin/snarkjs \
#     research/spikes/browser/run.sh
#
# BACKEND: a clone containing wamimi/Noir-Groth16@828025f (not modified; a worktree is made
#   under target/). NARGO: 1.0.0-beta.18. SNARKJS: snarkjs 0.7.5 installed with npm, so that
#   build/snarkjs.min.js sits next to it.
# Needs: `rustup target add wasm32-unknown-unknown --toolchain 1.95.0`.
# FULL=1 also prepares three note circuits (17k to 55k constraints); this generates a
#   development 2^16 powers-of-tau file, which takes several minutes.
# Open the printed URL in a browser. If Playwright is installed, the page is also measured in
# headless Chromium and the JSON printed.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
WORK="$ROOT/target/browser"
CARGO=${CARGO:-cargo +1.95.0}
PORT=${PORT:-8765}
: "${BACKEND:?}" "${NARGO:?}" "${SNARKJS:?}"
mkdir -p "$WORK"

# 1. The pinned backend, native (reference witnesses) and as wasm32.
rm -rf "$WORK/backend" && git clone -q "$BACKEND" "$WORK/backend"
git -C "$WORK/backend" checkout -q 828025f3a0090e2934940956c0f5dc8093eb5532
(cd "$WORK/backend" && $CARGO build --locked -p noir-cli)
rm -rf "$WORK/backend-wasm" && cp -R "$HERE/backend-wasm" "$WORK/backend-wasm"
sed "s|@BACKEND@|$WORK/backend|g" "$HERE/backend-wasm/Cargo.toml.in" > "$WORK/backend-wasm/Cargo.toml"
# getrandom 0.4 has no default backend on wasm32-unknown-unknown; the crate supplies one.
(cd "$WORK/backend-wasm" && RUSTFLAGS='--cfg getrandom_backend="custom"' $CARGO build --release --target wasm32-unknown-unknown)

# 2. The site.
WEB="$WORK/web"; rm -rf "$WEB"; mkdir -p "$WEB"
cp "$HERE/web/index.html" "$HERE/web/prove.js" "$WEB/"
cp "$WORK/backend-wasm/target/wasm32-unknown-unknown/release/backend_wasm.wasm" "$WEB/backend.wasm"
cp "$(cd "$(dirname "$SNARKJS")/../snarkjs/build" && pwd)/snarkjs.min.js" "$WEB/"
EXTRA=()
if [ "${FULL:-0}" = 1 ]; then
  python3 "$ROOT/research/spikes/shielded-notes/constraints.py" --nargo "$NARGO" \
    --backend-cli "$WORK/backend/target/debug/noir-cli" --snarkjs "$SNARKJS" --out "$WORK/shielded" --depths 20,32
  "$SNARKJS" powersoftau new bn128 16 "$WORK/p0.ptau" > /dev/null
  "$SNARKJS" powersoftau contribute "$WORK/p0.ptau" "$WORK/p1.ptau" --name=spike -e="public spike entropy, development only" > /dev/null
  "$SNARKJS" powersoftau prepare phase2 "$WORK/p1.ptau" "$WORK/final16.ptau" > /dev/null
  EXTRA=(--shielded "$WORK/shielded" --ptau "$WORK/final16.ptau")
fi
python3 "$HERE/prepare.py" --repo "$ROOT" --nargo "$NARGO" --backend-cli "$WORK/backend/target/debug/noir-cli" \
  --snarkjs "$SNARKJS" --web "$WEB" ${EXTRA[@]+"${EXTRA[@]}"}

# 3. Serve and measure.
(cd "$WEB" && python3 -m http.server "$PORT" > /dev/null 2>&1) &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
echo "page: http://localhost:$PORT/   (add ?runs=5 for more runs)"
if node -e "require('playwright')" 2>/dev/null; then
  node "$HERE/measure.cjs" "http://localhost:$PORT/" "${RUNS:-3}"
else
  echo "Playwright not found: open the page in a browser and read the table. Press Enter to stop the server."
  read -r _
fi

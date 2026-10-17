#!/usr/bin/env bash
# Build or run the pinned Linux counter and private tally container (local, no-wallet modes only).
#
#   scripts/run-counter-container.sh build      # downloads toolchains (network)
#   scripts/run-counter-container.sh doctor     # prerequisite checks, no network
#   scripts/run-counter-container.sh quick      # fresh proof + signed local lifecycle
#   scripts/run-counter-container.sh local      # quick + 48 VM cases, ranges, 3 mutations
#   scripts/run-counter-container.sh tally-quick  # private tally: setup + signed local lifecycle
#   scripts/run-counter-container.sh tally-local  # tally-quick + 49 VM cases, 4 mutations
#
# Runs use --network none: the local CKB chain lives on the container's loopback
# and nothing is downloaded at run time. Results land in target/container-runs/.
set -euo pipefail

IMAGE="${COUNTER_IMAGE:-noir-ckb-counter}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-}"

case "$MODE" in
  build)
    # Stamp what the image is built from, so runs report the image's source, not the host's.
    exec docker build -f "$ROOT/containers/counter/Dockerfile" -t "$IMAGE" \
      --label "org.noir-ckb.source-revision=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)" \
      --label "org.noir-ckb.source-dirty-paths=$(git -C "$ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' ')" \
      --label "org.noir-ckb.dockerfile-sha256=$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$ROOT/containers/counter/Dockerfile")" \
      --label "org.noir-ckb.base-image=$(sed -n 's/^ARG BASE=//p' "$ROOT/containers/counter/Dockerfile")" \
      "$ROOT" ;;
  doctor|quick|local|tally-quick|tally-local) ;;
  *)
    sed -n '2,12p' "$0"; exit 2 ;;
esac

docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "Image $IMAGE not found. Run: $0 build" >&2; exit 1; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
HOST_DIR="$ROOT/target/container-runs/$MODE-$STAMP"
mkdir -p "$HOST_DIR"

USER_ARGS=()
if [ "$(uname -s)" = "Linux" ]; then
  USER_ARGS=(--user "$(id -u):$(id -g)")
fi

json_string() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }
{
  echo "{"
  echo "  \"mode\": $(json_string "$MODE"),"
  echo "  \"started_utc\": $(json_string "$STAMP"),"
  echo "  \"image\": $(json_string "$IMAGE"),"
  echo "  \"image_id\": $(json_string "$(docker image inspect "$IMAGE" --format '{{.Id}}')"),"
  echo "  \"image_architecture\": $(json_string "$(docker image inspect "$IMAGE" --format '{{.Os}}/{{.Architecture}}')"),"
  echo "  \"image_labels\": $(docker image inspect "$IMAGE" --format '{{json .Config.Labels}}'),"
  echo "  \"docker_server\": $(json_string "$(docker version --format '{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}' 2>/dev/null || echo unknown)"),"
  echo "  \"host\": $(json_string "$(uname -sm)"),"
  echo "  \"host_checkout_revision\": $(json_string "$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"),"
  echo "  \"host_checkout_dirty_paths\": $(git -C "$ROOT" status --porcelain 2>/dev/null | wc -l | tr -d ' '),"
  echo "  \"network\": \"none\""
  echo "}"
} > "$HOST_DIR/container-provenance.json"

ARGS=("$MODE")
if [ "$MODE" != "doctor" ]; then
  ARGS+=(--yes --out "target/runs/run")
fi

set +e
# ${arr[@]+...} keeps macOS bash 3.2 happy with an empty array under set -u.
docker run --rm --network none ${USER_ARGS[@]+"${USER_ARGS[@]}"} \
  -v "$HOST_DIR:/opt/noir-ckb-verifier/target/runs" \
  "$IMAGE" "${ARGS[@]}" 2>&1 | tee "$HOST_DIR/console.log"
CODE="${PIPESTATUS[0]}"
set -e
echo "$CODE" > "$HOST_DIR/exit-code"
echo "Container exit $CODE. Results: $HOST_DIR (share only manifest.json, container-provenance.json and sanitized errors)."
exit "$CODE"

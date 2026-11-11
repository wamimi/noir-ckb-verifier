#!/usr/bin/env bash
# R1 spike: does the pinned Noir-Groth16 backend accept Noir 1.0.0-rc ACIR?
# Usage:
#   NARGO_OLD=/path/to/nargo-1.0.0-beta.18 NARGO_NEW=/path/to/nargo-1.0.0-rc.N \
#   BACKEND=/path/to/Noir-Groth16 SNARKJS=/path/to/snarkjs research/spikes/noir-1x/run.sh
# BACKEND must be a clone containing revision 828025f (wamimi/Noir-Groth16). It is not
# modified: the patch is applied to a copy under target/noir-1x. The circuits are copied
# before compiling; circuits/private-tally-v2 and ceremony/ are only read.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
WORK="$ROOT/target/noir-1x"
CARGO=${CARGO:-cargo +1.95.0}
: "${NARGO_OLD:?}" "${NARGO_NEW:?}" "${BACKEND:?}" "${SNARKJS:?}"
rm -rf "$WORK"; mkdir -p "$WORK"
git clone -q "$BACKEND" "$WORK/backend" && git -C "$WORK/backend" checkout -q 828025f3a0090e2934940956c0f5dc8093eb5532
git clone -q "$WORK/backend" "$WORK/backend-patched" && git -C "$WORK/backend-patched" checkout -q 828025f3a0090e2934940956c0f5dc8093eb5532
git -C "$WORK/backend-patched" apply "$HERE/backend-noir-1x.patch"
(cd "$WORK/backend" && $CARGO build --locked -p noir-cli)
(cd "$WORK/backend-patched" && $CARGO build -p noir-cli)   # not --locked: the patch adds a dependency
PINNED="$WORK/backend/target/debug/noir-cli"; PATCHED="$WORK/backend-patched/target/debug/noir-cli"
probe() { python3 "$HERE/probe.py" --label "$1" --nargo "$2" --backend-cli "$3" --snarkjs "$SNARKJS" --repo "$ROOT" --work "$WORK/$4" ${5:+--poseidon $5} > /dev/null; \
  python3 -c "import json,sys;r=json.load(open(sys.argv[1]));print(r['label'],'| compile:',r['compile'][:60],'| backend:',r.get('update_backend','-')[:50],'| frozen R1CS:',r.get('update_r1cs_is_frozen_ceremony_r1cs'),'| ceremony-key proof:',r.get('update_ceremony_key_proof'))" "$WORK/$4/result.json"; }
probe "old Nargo, committed circuit, pinned backend"   "$NARGO_OLD" "$PINNED"  a
probe "old Nargo, poseidon v0.4.0, pinned backend"     "$NARGO_OLD" "$PINNED"  b v0.4.0
probe "new Nargo, committed circuit, pinned backend"   "$NARGO_NEW" "$PINNED"  c
probe "new Nargo, poseidon v0.4.0, pinned backend"     "$NARGO_NEW" "$PINNED"  d v0.4.0
probe "new Nargo, poseidon v0.4.0, patched backend"    "$NARGO_NEW" "$PATCHED" e v0.4.0
probe "old Nargo, committed circuit, patched backend"  "$NARGO_OLD" "$PATCHED" f
python3 "$HERE/survey.py" --old "$NARGO_OLD" --new "$NARGO_NEW" --backend-cli "$PATCHED" --repo "$ROOT" --work "$WORK/survey" \
  | python3 -c "
import json,sys
for l in sys.stdin:
    d=json.loads(l); print(d['circuit'],'| same ACIR program:',d['same_program'],'| same R1CS:',d['same_r1cs'],'| new decode:',d['new_decode'])"

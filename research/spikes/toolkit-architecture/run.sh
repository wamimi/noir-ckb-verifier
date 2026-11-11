#!/usr/bin/env bash
# Lints the five draft specs, then replays the two existing applications against recorded
# CKB-VM matrix runs. Usage: research/spikes/toolkit-architecture/run.sh
# The matrix directories are produced by scripts/check-private-tally.py and
# scripts/check-owned-counter.py (override with TALLY_RUN / COUNTER_RUN).
set -euo pipefail
cd "$(dirname "$0")/../../.."
S=research/spikes/toolkit-architecture
TALLY_RUN=${TALLY_RUN:-target/tally-testnet/local/matrix}
COUNTER_RUN=${COUNTER_RUN:-target/week-15-guided-validation-20261009}
j() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]));[d:=d[k] for k in sys.argv[2:]];print(d)" "$@"; }

python3 $S/bindspec.py lint $S/specs/private-tally.toml --noir circuits/private-tally-v2/circuit/src/main.nr
python3 $S/bindspec.py lint $S/specs/owned-counter.toml --noir circuits/owned-counter-v1/src/main.nr
python3 $S/bindspec.py lint $S/specs/ballot-box.toml $S/specs/shielded-pool.toml $S/specs/battleship.toml

B=$TALLY_RUN/build.json
python3 $S/bindspec.py replay $S/specs/private-tally.toml --cases $TALLY_RUN/cases \
  --pin self=$(j $B code_hash) --pin network=$(j $B network_domain) \
  --pin guard=$(j $B guard_data_hash) --pin vk.tally=$(j $B vk_data_hash)

B=$COUNTER_RUN/build/build.json
SELF=$(python3 -c "import json;print(json.load(open('$COUNTER_RUN/matrix/update-valid.json'))['transaction']['outputs'][0]['type']['code_hash'])")
python3 $S/bindspec.py replay $S/specs/owned-counter.toml --cases $COUNTER_RUN/matrix \
  --pin self=$SELF --pin network=$(j $B env COUNTER_NETWORK_DOMAIN) \
  --pin owner_code=$(j $B env COUNTER_OWNER_CODE_HASH) --pin owner_data=$(j $B env COUNTER_OWNER_DATA_HASH) \
  --pin vk.counter=$(j $B env COUNTER_VK_DATA_HASH)

# Negative lint: deliberately unsafe edits of the draft specs. Each must be refused.
python3 $S/negative_lint.py

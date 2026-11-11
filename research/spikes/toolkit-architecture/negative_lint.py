#!/usr/bin/env python3
"""Negative lint: each entry edits one draft spec into an unsafe one. The linter must refuse all."""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = [  # name, spec, text to replace, replacement
    ("vote-bound-to-outpoint", "ballot-box", '"action", "public.nullifier"', '"action", "in.outpoint", "public.nullifier"'),
    ("vote-reads-running-total", "ballot-box", 'choice = "witness"', 'choice = "in.data.yes"'),
    ("battleship-joiner-rewrites-opponent", "battleship", 'change = ["capacity", "data.status",', 'change = ["capacity", "data.timeout", "data.status",'),
    ("battleship-free-field-outside-context", "battleship", '"action", "out.data", "out.capacity"]', '"action", "out.capacity"]'),
    ("ballot-created-capacity-unstated", "ballot-box", 'free = ["capacity", ', 'free = ['),
    ("vote-may-replace-voter-root", "ballot-box", '"data.total"]', '"data.total", "data.voter_root"]'),
    ("tally-update-without-outpoint", "private-tally", '"in.outpoint", ', ""),
    ("tally-commitment-unbound", "private-tally", 'c_new = "out.data.commitment", ctx_lo = "context.lo", ctx_hi = "context.hi" }\ncontext = [\n  "tag:noir-ckb/private-tally/context/v2", "network", "profile", "script_hash", "args.id", "action",\n  "in.outpoint"',
     'c_new = "witness", ctx_lo = "context.lo", ctx_hi = "context.hi" }\ncontext = [\n  "tag:noir-ckb/private-tally/context/v2", "network", "profile", "script_hash", "args.id", "action",\n  "in.outpoint"'),
    ("battleship-swap-incomplete", "battleship", '  { left = "out.data.waiter_lock", op = "eq", right = "in.data.mover_lock" },\n', ""),
    ("battleship-order-on-hash", "battleship", '{ left = "in.data.status", op = "le", const = 1 }', '{ left = "in.data.waiter_lock", op = "le", const = 1 }'),
    ("battleship-fields-differ-in-width", "battleship", 'right = "in.data.mover_hits"', 'right = "in.data.mover_shots"'),
    ("counter-created-unbound", "owned-counter", 'signer = "out.lock_hash"\n', ""),
]
failed = 0
with tempfile.TemporaryDirectory() as tmp:
    for name, spec, old, new in CASES:
        text = (HERE / "specs" / f"{spec}.toml").read_text()
        assert text.count(old) >= 1, f"{name}: edit does not apply"
        path = Path(tmp) / f"{name}.toml"
        path.write_text(text.replace(old, new, 1))
        q = subprocess.run([sys.executable, str(HERE / "bindspec.py"), "lint", str(path)], capture_output=True, text=True)
        errors = [line.strip()[7:] for line in q.stdout.splitlines() if line.strip().startswith("error:")]
        if q.returncode == 0:
            failed += 1
            print(f"NOT REFUSED: {name}")
        else:
            print(f"refused as expected: {name}: {errors[0]}")
print(f"{len(CASES) - failed} of {len(CASES)} unsafe specs refused")
sys.exit(1 if failed else 0)

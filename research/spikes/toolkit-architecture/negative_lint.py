#!/usr/bin/env python3
"""Negative lint: each entry edits one draft spec into an unsafe or malformed one.

The linter must refuse every entry, and one of its errors must contain the expected text:
a refusal for an unrelated reason counts as a failure of the test, not as a pass.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TALLY_UPDATE = ('c_new = "out.data.commitment", ctx_lo = "context.lo", ctx_hi = "context.hi" }\ncontext = [\n'
                '  "tag:noir-ckb/private-tally/context/v2", "network", "profile", "script_hash", "args.id", "action",\n  "in.outpoint"')
OPEN_CONTEXT = '"action", "out.data", "out.capacity"]'  # first occurrence: the `open` action
CASES = [  # name, spec, [(text to replace, replacement), ...], text one error must contain
    ("vote-bound-to-outpoint", "ballot-box", [('"action", "public.nullifier"', '"action", "in.outpoint", "public.nullifier"')], "in.outpoint"),
    ("vote-reads-running-total", "ballot-box", [('choice = "witness"', 'choice = "in.data.yes"')], "shared"),
    ("battleship-joiner-rewrites-opponent", "battleship", [('change = ["capacity", "data.status",', 'change = ["capacity", "data.timeout", "data.status",')], "field timeout may differ"),
    ("battleship-free-field-outside-context", "battleship", [(OPEN_CONTEXT, '"action", "out.capacity"]')], "must be in the context"),
    ("ballot-created-capacity-unstated", "ballot-box", [('free = ["capacity", ', 'free = [')], "the capacity may differ"),
    ("vote-may-replace-voter-root", "ballot-box", [('"data.total"]', '"data.total", "data.voter_root"]')], "field voter_root may differ"),
    ("tally-update-without-outpoint", "private-tally", [('"in.outpoint", ', "")], "in.outpoint"),
    ("tally-commitment-unbound", "private-tally", [(TALLY_UPDATE, TALLY_UPDATE.replace('c_new = "out.data.commitment"', 'c_new = "witness"'))], "field commitment may differ"),
    ("battleship-swap-incomplete", "battleship", [('  { left = "out.data.waiter_lock", op = "eq", right = "in.data.mover_lock" },\n', "")], "field waiter_lock may differ"),
    ("battleship-order-on-hash", "battleship", [('{ left = "in.data.status", op = "le", const = 1 }', '{ left = "in.data.waiter_lock", op = "le", const = 1 }')], "order"),
    ("battleship-fields-differ-in-width", "battleship", [('right = "in.data.mover_hits"', 'right = "in.data.mover_shots"')], "width"),
    ("counter-created-unbound", "owned-counter", [('signer = "out.lock_hash"\n', "")], "may differ"),
    # External review, finding 1: the Lock and the capacity get the same analysis as data.
    ("tally-created-capacity-context-only", "private-tally", [('free = ["capacity"]', 'free = []')], "only the context covers it"),
    ("battleship-open-capacity-context-only", "battleship", [('free = ["capacity", "timeout", ', 'free = ["timeout", ')], "only the context covers it"),
    ("join-capacity-context-only", "battleship", [('stake_out = "out.capacity"', 'stake_out = "witness"')], "the capacity may differ"),
    ("counter-update-lock-context-only", "owned-counter", [('change = ["data.count"]', 'change = ["data.count", "lock"]')], "the Lock may differ"),
    ("free-capacity-outside-context", "battleship", [(OPEN_CONTEXT, '"action", "out.data"]')], "free the capacity must be in the context"),
    ("free-lock-outside-context", "owned-counter", [('change = ["data.count"]', 'change = ["data.count", "lock"]\nfree = ["lock"]'), ('"out.lock_hash", "out.capacity",\n]', '"out.capacity",\n]')], "free the Lock must be in the context"),
    # Finding 2: an equality pins a field only if its other side is anchored; a 32-byte
    # value is proven only when both halves are public inputs.
    ("equality-with-free-field", "battleship", [('right = "in.data.waiter_lock" },\n]\nfree', 'right = "out.data.waiter_lock" },\n]\nfree')], "itself not anchored"),
    ("equality-cycle", "battleship", [('{ left = "out.data.mover_board", op = "eq", right = "in.data.waiter_board" },\n  { left = "out.data.waiter_board", op = "eq", right = "in.data.mover_board" },',
                                       '{ left = "out.data.mover_board", op = "eq", right = "out.data.waiter_board" },\n  { left = "out.data.waiter_board", op = "eq", right = "out.data.mover_board" },')], "itself not anchored"),
    ("lock-half-public", "owned-counter", [('public = ["old_count", "new_count", "context_lo"', 'public = ["old_count", "new_count", "lock_lo", "context_lo"'),
                                           ('new_count = "out.data.count", ', 'new_count = "out.data.count", lock_lo = "out.lock_hash:lo", '),
                                           ('change = ["data.count"]', 'change = ["data.count", "lock"]')], "only one half"),
    # Finding 5: `signer` exempts nothing unless the Lock rule pins the code and declares what it signs.
    ("signer-without-signing-policy", "owned-counter", [(', signs = "transaction" }', ' }')], "signer gives no exemption"),
    ("signer-is-not-the-cell-lock", "owned-counter", [('signer = "out.lock_hash"', 'signer = "witness"')], "signer"),
    # Finding 10: sizes and closed enumerations.
    ("seventeen-public-inputs", "private-tally", [('public = ["c_old", "c_new", "ctx_lo", "ctx_hi"]', 'public = ["c_old", "c_new", "ctx_lo", "ctx_hi", ' + ", ".join(f'"p{i}"' for i in range(13)) + "]")], "more than 16"),
    ("zero-count", "battleship", [('{ name = "timeout", type = "u32" }', '{ name = "timeout", type = "u32", count = 0 }')], "count must be a positive integer"),
    ("spawn-under-data1", "battleship", [('hash_type = "data2" ', 'hash_type = "data1" ')], "needs hash_type"),
    ("unknown-envelope", "private-tally", [('envelope = "bare"', 'envelope = "v3"')], "envelope must be"),
    ("unknown-since-kind", "battleship", [('kind = "relative-blocks"', 'kind = "relative-block"')], "since.kind"),
    ("since-from-unknown-source", "battleship", [('min = "in.data.timeout"', 'min = "in.data.deadline"')], "deadline"),
]
failed = 0
with tempfile.TemporaryDirectory() as tmp:
    for name, spec, edits, expect in CASES:
        text = (HERE / "specs" / f"{spec}.toml").read_text()
        for old, new in edits:
            assert text.count(old) >= 1, f"{name}: edit does not apply"
            text = text.replace(old, new, 1)
        path = Path(tmp) / f"{name}.toml"
        path.write_text(text)
        q = subprocess.run([sys.executable, str(HERE / "bindspec.py"), "lint", str(path)], capture_output=True, text=True)
        errors = [line.strip()[7:] for line in q.stdout.splitlines() if line.strip().startswith("error:")]
        hit = [e for e in errors if expect in e]
        if q.returncode == 0:
            failed += 1
            print(f"NOT REFUSED: {name}")
        elif not hit:
            failed += 1
            print(f"REFUSED FOR ANOTHER REASON: {name}: wanted '{expect}', got {errors or q.stderr.strip().splitlines()[-1:]}")
        else:
            print(f"refused as expected: {name}: {hit[0]}")
print(f"{len(CASES) - failed} of {len(CASES)} unsafe specs refused for the expected reason")
sys.exit(1 if failed else 0)

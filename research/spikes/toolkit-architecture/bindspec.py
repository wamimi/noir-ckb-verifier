#!/usr/bin/env python3
"""Reference reader for the draft [binding] format 2 (research/toolkit-architecture.md).

  lint    check one or more spec files against the format rules
  replay  evaluate a spec against recorded CKB-VM matrix cases and compare the
          predicted outcome of every case with the outcome CKB-VM recorded

This is a research spike, not the generator. It evaluates every rule of a spec
except the pairing check, so a case the spec lets through is reported as PAIRING.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

P = 21888242871839275222246405745257275088548364400416034343698204186575808495617
HASH_TYPE = {"data": 0, "type": 1, "data1": 2, "data2": 4}
WIDTH = {"u8": 1, "u16": 2, "u32": 4, "u64": 8, "u128": 16, "field": 32, "bytes32": 32, "type_id": 32}
SHAPES = {"create": (0, 1), "update": (1, 1), "destroy": (1, 0), "spend": (1, 0)}
# Stable error codes of generated scripts (40-54 are the codes the two existing scripts use).
E = dict(LOAD=40, ARGS=41, SHAPE=42, STATE=43, ID=44, LOCK=45, OWNER=46, CAPACITY=47, WITNESS=48, PUBLIC=49,
         VK=50, PROOF=51, LIMIT=52, REQUIRE=53, FIELD=54, KEEP=55, SINCE=56, OUTPUT=57, EFFECT=58)
MAX_CELLS = 64
MANDATORY_CONTEXT = ("network", "profile", "script_hash", "action")
OPS = ("eq", "ne", "lt", "le", "gt", "ge")
EFFECT_OPS = {"set-insert": "R2", "tree-append": "R2", "add": "R2", "capacity-add": "R2", "capacity-sub": "R2"}


def h(b):
    return hashlib.blake2b(b, digest_size=32, person=b"ckb-default-hash").digest()


def raw(s):
    return bytes.fromhex(s[2:] if s.startswith("0x") else s)


def u32(n):
    return n.to_bytes(4, "little")


def ser_script(s):
    parts = [raw(s["code_hash"]), bytes([HASH_TYPE[s["hash_type"]]]), u32(len(raw(s["args"]))) + raw(s["args"])]
    head = 4 + 4 * len(parts)
    offsets, pos = [], head
    for p in parts:
        offsets.append(pos)
        pos += len(p)
    return u32(pos) + b"".join(u32(o) for o in offsets) + b"".join(parts)


def script_hash(s):
    return h(ser_script(s))


def outpoint(p):
    return raw(p["tx_hash"]) + u32(int(p["index"], 16))


class Reject(Exception):
    def __init__(self, code):
        self.code = E[code]


class Spec:
    def __init__(self, path):
        self.path = Path(path)
        self.b = tomllib.loads(self.path.read_text())["binding"]
        self.cell = self.b.get("cell", {})
        self.actions = self.b.get("action", [])
        self.circuits = self.b.get("circuit", {})

    @staticmethod
    def layout(fields):
        """name -> (offset, width, field); total width. All fields are fixed width."""
        out, pos = {}, 0
        for f in fields:
            w = WIDTH[f["type"]] * f.get("count", 1)
            out[f["name"]] = (pos, w, f)
            pos += w
        return out, pos

    # ------------------------------------------------------------------ lint
    def lint(self, noir=None):
        err, warn, b = [], [], self.b
        if b.get("format") != 2:
            err.append("format must be 2")
        placement = b.get("placement", "type")
        if placement not in ("type", "lock"):
            err.append("placement must be type or lock")
        envelope = b.get("envelope", "v1")
        if not re.fullmatch(r"[a-z0-9./-]+", b.get("profile", "")):
            err.append("profile must be a lowercase ASCII path")
        for part in ("args", "data"):
            names = [f["name"] for f in self.cell.get(part, [])]
            if len(names) != len(set(names)):
                err.append(f"cell.{part}: duplicate field name")
            for f in self.cell.get(part, []):
                if f["type"] not in WIDTH:
                    err.append(f"cell.{part}.{f['name']}: unknown type {f['type']}")
        data, _ = self.layout([f for f in self.cell.get("data", []) if f["type"] in WIDTH])
        args, _ = self.layout([f for f in self.cell.get("args", []) if f["type"] in WIDTH])
        ids = [a.get("id") for a in self.actions]
        if len(ids) != len(set(ids)) or any(not isinstance(i, int) or not 0 <= i < 256 for i in ids):
            err.append("action ids must be distinct integers below 256")
        shapes = [a.get("shape") for a in self.actions]
        if any(s not in SHAPES for s in shapes):
            err.append("unknown shape")
        if placement == "lock" and any(s != "spend" for s in shapes):
            err.append("placement = lock allows only the spend shape")
        if envelope == "bare" and len(shapes) != len(set(shapes)):
            err.append("envelope = bare needs one action per shape; use envelope = v1")
        modified = set()  # data fields some action changes
        gated = []  # actions outside generator version 2 (shared Cells, effects)
        for a in self.actions:
            modified |= {c[5:] for c in a.get("change", []) if c.startswith("data.")}
        for a in self.actions:
            n, shape = a.get("name", "?"), a.get("shape")
            has_in, has_out = shape in ("update", "destroy", "spend"), shape in ("create", "update")
            atoms = list(a.get("public", {}).values()) + a.get("context", [])
            for e in a.get("effects", []):
                atoms += [v for k, v in e.items() if k != "op" and isinstance(v, str)]
                if e.get("op") not in EFFECT_OPS:
                    err.append(f"{n}: unknown effect {e.get('op')}")
                else:
                    warn.append(f"{n}: effect {e['op']} is provisional until {EFFECT_OPS[e['op']]} fixes its cost and encoding")
            for o in a.get("outputs", {}).values():
                atoms += [v for v in o.values() if isinstance(v, str)]
            pinned = set()  # successor fields fixed by an equality check
            for r in a.get("require", []):
                atoms += [r[k] for k in ("left", "right") if isinstance(r.get(k), str)]
                if r.get("op") not in OPS or ("const" in r) == ("right" in r) or "left" not in r:
                    err.append(f"{n}: a check needs left, op in {OPS} and exactly one of const, right")
                elif "right" in r and r["op"] != "eq":
                    err.append(f"{n}: a field-from-field check supports only eq")
                elif "right" in r and self.width(r["left"], data, args) != self.width(r["right"], data, args):
                    err.append(f"{n}: {r['left']} and {r['right']} differ in width")
                elif r["op"] not in ("eq", "ne") and self.width(r["left"], data, args) > 16:
                    err.append(f"{n}: ordering checks need an integer of at most 128 bits")
                m = re.fullmatch(r"out\.data\.(\w+)", r.get("left", ""))
                if m and r.get("op") == "eq":
                    pinned.add(m.group(1))
            if a.get("shared") or a.get("effects"):
                gated.append(n)
            for atom in atoms:
                problem = self.check_atom(atom, a, has_in, has_out, placement, data, args)
                if problem:
                    err.append(f"{n}: {atom}: {problem}")
            circuit = a.get("circuit")
            if circuit is None:
                if a.get("public") or a.get("context"):
                    err.append(f"{n}: public/context without a circuit")
                if shape == "create" and not a.get("signer"):
                    unbound = [f for f, (_, _, d) in data.items() if "const" not in d and f not in pinned
                               and f not in a.get("free", [])]
                    if unbound:
                        err.append(f"{n}: created without proof or signer, unbound fields {unbound}")
                elif a.get("signer"):
                    warn.append(f"{n}: relies on the signer's Lock covering the whole transaction (sighash-all)")
            else:
                if circuit not in self.circuits:
                    err.append(f"{n}: unknown circuit {circuit}")
                    continue
                declared, mapped = self.circuits[circuit].get("public", []), a.get("public", {})
                if set(declared) != set(mapped):
                    err.append(f"{n}: public map must cover exactly {declared}")
                srcs = list(mapped.values())
                if srcs.count("context.lo") != 1 or srcs.count("context.hi") != 1:
                    err.append(f"{n}: exactly one public for context.lo and one for context.hi")
                ctx = a.get("context", [])
                if not ctx or not ctx[0].startswith("tag:"):
                    err.append(f"{n}: context must start with a tag")
                for item in MANDATORY_CONTEXT:
                    if item not in ctx:
                        err.append(f"{n}: context lacks {item}")
                inserts = {e.get("key") for e in a.get("effects", []) if e.get("op") == "set-insert"}
                anchors = [c for c in ctx if c in ("in.outpoint", "tx_hash") or c in inserts
                           or (shape == "create" and c.startswith("args.") and args.get(c[5:], (0, 0, {}))[2].get("type") == "type_id")]
                if not anchors:
                    err.append(f"{n}: no freshness anchor (in.outpoint, tx_hash, a type_id on create, or an inserted nullifier)")
                for name, src in mapped.items():
                    used = f"public.{name}" in ctx or any(f"public.{name}" in e.values() for e in a.get("effects", [])) \
                        or any(f"public.{name}" in o.values() for o in a.get("outputs", {}).values())
                    if src == "witness" and not used:
                        err.append(f"{n}: public {name} comes from the witness and is used nowhere")
                if a.get("shared"):
                    for atom in srcs + ctx:  # effects may read mutable state; the proof may not
                        m = re.fullmatch(r"(in|out)\.data\.(\w+)(:lo|:hi)?", atom)
                        if atom in ("in.outpoint", "tx_hash", "in.data", "out.data", "in.capacity", "out.capacity"):
                            err.append(f"{n}: shared action reads {atom}, which changes when another user goes first")
                        elif m and m.group(2) in modified:
                            err.append(f"{n}: shared action reads mutable field {m.group(2)}")
            statement = {m.group(1) for v in a.get("public", {}).values()
                         for m in [re.fullmatch(r"out\.data\.(\w+)(:lo|:hi)?", v)] if m}
            in_context = set(data) if "out.data" in a.get("context", []) else {
                c[9:] for c in a.get("context", []) if c.startswith("out.data.")}
            free = set(a.get("free", []))
            for f in sorted(free & set(data)):
                if circuit and f not in in_context:
                    err.append(f"{n}: free field {f} must be in the context, or a third party can replace it")
            if shape == "create":
                if circuit:
                    for f, (_, _, d) in data.items():
                        if "const" not in d and f not in pinned | statement | free:
                            err.append(f"{n}: field {f} is neither proven, pinned nor declared free at creation"
                                       + (" (only the context covers it: the prover can set it to anything)" if f in in_context else ""))
                lock_rule = self.cell.get("lock", {})
                if not a.get("signer"):
                    if "args" not in lock_rule and "out.lock_hash" not in atoms and "lock" not in free:
                        err.append(f"{n}: the Lock of the created Cell is bound nowhere and not declared free")
                    if "out.capacity" not in atoms and "capacity" not in free:
                        err.append(f"{n}: the capacity of the created Cell is bound nowhere and not declared free")
            if shape == "update":
                bound = pinned | statement | (free & in_context if circuit else free)
                for e in a.get("effects", []):
                    for v in e.values():
                        m = re.fullmatch(r"out\.data\.(\w+)", v) if isinstance(v, str) else None
                        if m:
                            bound.add(m.group(1))
                changed = {c[5:] for c in a.get("change", []) if c.startswith("data.")}
                for f in sorted(changed - set(data)):
                    err.append(f"{n}: change names unknown field {f}")
                for f in sorted(changed & set(data)):
                    if f not in bound:
                        err.append(f"{n}: field {f} may change but is neither proven, pinned, an effect target nor declared free"
                                   + (" (only the context covers it: the prover can set it to anything)" if f in in_context else ""))
                for f in a.get("change", []):
                    if f in ("capacity", "lock"):
                        key = "out.capacity" if f == "capacity" else "out.lock_hash"
                        if key not in atoms and not any(e.get("op", "").startswith("capacity") for e in a.get("effects", [])) \
                                and f not in a.get("free", []):
                            err.append(f"{n}: {f} may change but is bound nowhere")
            names = list(a.get("outputs", {}))
            if len(names) != len(set(names)):
                err.append(f"{n}: duplicate named output")
        if noir:
            text = Path(noir).read_text()
            sig = re.search(r"fn main\((.*?)\)", text, re.S).group(1)
            pub = re.findall(r"(\w+)\s*:\s*pub\b", sig)
            for name, c in self.circuits.items():
                if c.get("public") == pub:
                    break
            else:
                err.append(f"no circuit lists the Noir public parameters in order: {pub}")
        if gated:
            warn.append("generator version 2 will not generate this spec: shared mode or effects in "
                        + ", ".join(gated) + " (specified, gated on R2)")
        return err, warn

    @staticmethod
    def width(atom, data, args):
        fixed = {"outpoint": 36, "capacity": 8, "since": 8, "lock_hash": 32, "type_hash": 32, "data_hash": 32}
        head, _, rest = atom.partition(".")
        if rest.startswith("data.") and rest[5:] in data:
            return data[rest[5:]][1]
        if head == "args" and rest in args:
            return args[rest][1]
        return fixed.get(rest, 32)

    def check_atom(self, atom, a, has_in, has_out, placement, data, args):
        base = re.sub(r":(lo|hi)$", "", atom)
        if base.startswith(("tag:", "zero:", "const:", "pin:", "any:")) or base in (
                "zero", "witness", "context.lo", "context.hi", "tx_hash", *MANDATORY_CONTEXT):
            if base.startswith("any:"):
                return self.check_atom(base[4:], a, has_in, has_out, placement, data, args)
            return None
        head, _, rest = base.partition(".")
        if head == "public":
            ok = rest in self.circuits.get(a.get("circuit"), {}).get("public", [])
            return None if ok else "not a public input of this action's circuit"
        if head == "aux":
            return None if rest.isdigit() else "aux items are numbered"
        if head == "args":
            return None if rest in args else "unknown args field"
        if head in a.get("outputs", {}):
            return None if rest in ("lock_hash", "capacity", "type_hash", "data_hash") else "unknown output property"
        if head in ("in", "out"):
            if head == "in" and not has_in:
                return "this shape consumes no Cell"
            if head == "out" and (not has_out or placement == "lock"):
                return "this shape or placement has no successor Cell"
            if rest in ("data", "lock_hash", "capacity") or (head == "in" and rest in ("outpoint", "since")):
                return None
            if rest.startswith("data.") and rest[5:] in data:
                return None
        return "unknown source"


# ---------------------------------------------------------------------- replay
class Tx:
    def __init__(self, case):
        self.tx = case["transaction"]
        self.cells = {json.dumps(c["out_point"], sort_keys=True): c for c in case["cells"]}
        self.inputs = [self.cell(i["previous_output"]) for i in self.tx["inputs"]]
        self.outputs = [dict(output=o, data=d) for o, d in zip(self.tx["outputs"], self.tx["outputs_data"])]
        self.deps = []
        for d in self.tx["cell_deps"]:
            c = self.cell(d["out_point"])
            if d["dep_type"] == "dep_group":
                body = raw(c["data"])
                for k in range(int.from_bytes(body[:4], "little")):
                    m = body[4 + 36 * k: 40 + 36 * k]
                    self.deps.append(self.cell(dict(tx_hash="0x" + m[:32].hex(), index=hex(int.from_bytes(m[32:], "little")))))
            else:
                self.deps.append(c)

    def cell(self, p):
        return self.cells[json.dumps(dict(tx_hash=p["tx_hash"], index=p["index"]), sort_keys=True)]


def same_code(t, s):
    return t is not None and t["code_hash"] == s["code_hash"] and t["hash_type"] == s["hash_type"]


def witness_args(b):
    """Strict WitnessArgs: (lock, input_type, output_type), each bytes or None."""
    if len(b) < 16 or int.from_bytes(b[:4], "little") != len(b):
        raise Reject("WITNESS")
    offs = [int.from_bytes(b[4 + 4 * i: 8 + 4 * i], "little") for i in range(3)] + [len(b)]
    if offs[0] != 16 or sorted(offs) != offs:
        raise Reject("WITNESS")
    out = []
    for i in range(3):
        part = b[offs[i]: offs[i + 1]]
        if not part:
            out.append(None)
        elif len(part) >= 4 and int.from_bytes(part[:4], "little") == len(part) - 4:
            out.append(part[4:])
        else:
            raise Reject("WITNESS")
    return out


def wire_witness(b):
    """Strict groth16-ckb Groth16Witness v1 (schemas/groth16.mol): returns (proof, public vector bytes)."""
    def table(x, n):
        if len(x) < 4 + 4 * n or int.from_bytes(x[:4], "little") != len(x):
            raise Reject("WITNESS")
        offs = [int.from_bytes(x[4 + 4 * i: 8 + 4 * i], "little") for i in range(n)] + [len(x)]
        if offs[0] != 4 + 4 * n or sorted(offs) != offs:
            raise Reject("WITNESS")
        return [x[offs[i]: offs[i + 1]] for i in range(n)]
    version, content = table(b, 2)
    if len(version) != 2 or len(content) < 4 or content[:4] != u32(0):
        raise Reject("WITNESS")
    if version != b"\x01\x00":
        raise Reject("WITNESS")
    proof, public = table(content[4:], 2)
    if len(proof) != 128 or len(public) < 4 or len(public) != 4 + 32 * int.from_bytes(public[:4], "little"):
        raise Reject("WITNESS")
    return proof, public


class Run:
    """One script group of one transaction, evaluated in the generated check order."""

    def __init__(self, spec, pins, tx, script):
        self.s, self.pins, self.t, self.script = spec, pins, tx, script
        self.args_l, self.args_w = spec.layout(spec.cell["args"])
        self.data_l, self.data_w = spec.layout(spec.cell["data"])

    def pin(self, v):
        return self.pins[v[4:]] if v.startswith("pin:") else raw(v)

    def fixed(self, blob, layout, width, code):
        if len(blob) != width:
            raise Reject(code)
        for off, w, f in layout.values():
            if "const" in f and int.from_bytes(blob[off: off + w], "little") != f["const"]:
                raise Reject(code)

    def data(self, cell):
        blob = raw(cell["data"])
        self.fixed(blob, self.data_l, self.data_w, "STATE")
        for off, w, f in self.data_l.values():
            if f["type"] == "field":
                for k in range(f.get("count", 1)):
                    v = int.from_bytes(blob[off + 32 * k: off + 32 * k + 32], "little")
                    if v >= P or (f.get("nonzero") and v == 0):
                        raise Reject("FIELD")
        return blob

    def lock(self, cell):
        rule, lock = self.s.cell.get("lock"), cell["output"]["lock"]
        if not rule:
            return
        args = raw(lock["args"])
        if raw(lock["code_hash"]) != self.pin(rule["code_hash"]) or lock["hash_type"] != rule["hash_type"] \
                or ("args" in rule and args != raw(rule["args"])) or ("args_len" in rule and len(args) != rule["args_len"]):
            raise Reject("LOCK")
        if "dep_data_hash" in rule:
            hits = [d for d in self.t.deps if d["output"]["type"] and script_hash(d["output"]["type"]) == self.pin(rule["code_hash"])]
            if len(hits) != 1 or h(raw(hits[0]["data"])) != self.pin(rule["dep_data_hash"]):
                raise Reject("LOCK")

    def field(self, blob, layout, name):
        off, w, _ = layout[name]
        return blob[off: off + w]

    def atom(self, a, env):
        if a.startswith("tag:"):
            return a[4:].encode() + b"\0"
        if a.startswith("zero:"):
            return bytes(int(a[5:]))
        if a.startswith("const:"):
            return int(a[6:]).to_bytes(32, "little")
        if a.startswith("public."):
            return env["public"][a[7:]]
        if a.startswith("args."):
            return self.field(env["args"], self.args_l, a[5:])
        side, _, rest = a.partition(".")
        table = {
            "zero": lambda: bytes(32), "network": lambda: self.pins["network"],
            "profile": lambda: h(self.s.b["profile"].encode()), "script_hash": lambda: script_hash(self.script),
            "action": lambda: bytes([env["action"]["id"]]),
        }
        if a in table:
            return table[a]()
        cell = env[side]
        if rest == "data":
            return raw(cell["data"])
        if rest.startswith("data."):
            return self.field(raw(cell["data"]), self.data_l, rest[5:])
        if rest == "lock_hash":
            return script_hash(cell["output"]["lock"])
        if rest == "capacity":
            return int(cell["output"]["capacity"], 16).to_bytes(8, "little")
        if rest == "outpoint":
            return outpoint(cell["out_point"])
        raise SystemExit(f"replay does not evaluate {a}")

    def run(self):
        t, s, script = self.t, self.s, self.script
        args = raw(script["args"])
        try:
            self.fixed(args, self.args_l, self.args_w, "ARGS")
        except Reject:
            raise Reject("ARGS")
        if script["hash_type"] != s.b.get("hash_type", "data1"):
            raise Reject("ARGS")
        if max(len(t.inputs), len(t.outputs), len(t.deps)) >= MAX_CELLS:
            raise Reject("LIMIT")
        ins = [(i, c) for i, c in enumerate(t.inputs) if same_code(c["output"]["type"], script)]
        outs = [(i, c) for i, c in enumerate(t.outputs) if same_code(c["output"]["type"], script)]
        gin = [(i, c) for i, c in ins if c["output"]["type"] == script]
        gout = [(i, c) for i, c in outs if c["output"]["type"] == script]
        shape = (len(gin), len(gout))
        actions = [a for a in s.actions if SHAPES[a["shape"]] == shape]
        if len(ins) != len(gin) or len(outs) != len(gout) or len(actions) != 1:
            raise Reject("SHAPE")  # bare envelope: the shape selects the action
        action = actions[0]
        for name, (off, w, f) in self.args_l.items():
            if f["type"] == "type_id" and not gin:
                first = t.tx["inputs"][0]
                expect = h(int(first["since"], 16).to_bytes(8, "little") + outpoint(first["previous_output"])
                           + gout[0][0].to_bytes(8, "little"))
                if args[off: off + w] != expect:
                    raise Reject("ID")
        env = dict(action=action, args=args, public={})
        if gout:
            env["out"] = gout[0][1]
            self.lock(env["out"])
            self.data(env["out"])
        if gin:
            env["in"] = dict(gin[0][1], out_point=t.tx["inputs"][gin[0][0]]["previous_output"])
            self.lock(env["in"])
            self.data(env["in"])
        if gin and gout:
            change = action.get("change", [])
            if "lock" not in change and script_hash(env["in"]["output"]["lock"]) != script_hash(env["out"]["output"]["lock"]):
                raise Reject("OWNER")
            if "capacity" not in change and env["in"]["output"]["capacity"] != env["out"]["output"]["capacity"]:
                raise Reject("CAPACITY")
            for name in self.data_l:
                if "data." + name not in change and self.field(raw(env["in"]["data"]), self.data_l, name) \
                        != self.field(raw(env["out"]["data"]), self.data_l, name):
                    raise Reject("KEEP")
        for r in action.get("require", []):
            left = self.atom(r["left"], env)
            if "right" in r:
                ok = left == self.atom(r["right"], env)
            else:
                a, b = int.from_bytes(left, "little"), r["const"]
                ok = dict(eq=a == b, ne=a != b, lt=a < b, le=a <= b, gt=a > b, ge=a >= b)[r["op"]]
            if not ok:
                raise Reject("REQUIRE")
        if action.get("signer"):
            want = self.atom(action["signer"], env)
            if not any(script_hash(c["output"]["lock"]) == want for c in t.inputs):
                raise Reject("OWNER")
        if not action.get("circuit"):
            return "ACCEPT"
        # proof payload
        index = gin[0][0] if action["proof"] == "input_type" else gout[0][0]
        if index >= len(t.tx["witnesses"]):
            raise Reject("WITNESS")
        w = raw(t.tx["witnesses"][index])
        if len(w) > s.b.get("limits", {}).get("witness", 512):
            raise Reject("WITNESS")
        _, input_type, output_type = witness_args(w)
        payload = input_type if action["proof"] == "input_type" else output_type
        if payload is None:
            raise Reject("WITNESS")
        _, got = wire_witness(payload)
        names = s.circuits[action["circuit"]]["public"]
        pub = action["public"]
        for name in names:  # sources that do not depend on the context
            if not pub[name].startswith("context."):
                env["public"][name] = self.atom(pub[name], env).ljust(32, b"\0")
        digest = h(b"".join(self.atom(a, env) for a in action["context"]))
        for name in names:
            if pub[name] == "context.lo":
                env["public"][name] = digest[:16].ljust(32, b"\0")
            elif pub[name] == "context.hi":
                env["public"][name] = digest[16:].ljust(32, b"\0")
        expected = u32(len(names)) + b"".join(env["public"][n] for n in names)
        if got != expected:
            raise Reject("PUBLIC")
        vk = [d for d in t.deps if h(raw(d["data"])) == self.pins["vk." + action["circuit"]]]
        if len(vk) != 1:
            raise Reject("VK")
        return "PAIRING"


def predict(spec, pins, case):
    t = Tx(case)
    groups = []
    for c in t.inputs + t.outputs:
        ty = c["output"]["type"]
        if ty and raw(ty["code_hash"]) == pins["self"] and ty not in groups:
            groups.append(ty)
    results = []
    for g in groups:
        try:
            results.append(Run(spec, pins, t, g).run())
        except Reject as r:
            results.append(r.code)
    return results


def replay(a):
    spec = Spec(a.spec)
    err, _ = spec.lint()
    if err:
        raise SystemExit("spec does not lint: " + "; ".join(err))
    pins = {k: raw(v) for k, v in (p.split("=") for p in a.pin)}
    cases = Path(a.cases)
    rows, bad, lock_only = [], 0, 0
    for r in json.loads((cases / "results.json").read_text()):
        vm = r["result"]
        m = re.search(r"\.(Lock|Type), cause: ValidationFailure: see error code (-?\d+)", vm)
        predicted = predict(spec, pins, json.loads((cases / r["case"]).read_text()))
        if vm.startswith("Ok("):
            ok, shown = all(p in ("ACCEPT", "PAIRING") for p in predicted), "accepted"
        elif m and m.group(1) == "Lock":
            ok, shown = all(p in ("ACCEPT", "PAIRING") for p in predicted), f"Lock {m.group(2)}"
            lock_only += 1
        elif m and int(m.group(2)) == E["PROOF"]:
            ok, shown = all(p == "PAIRING" for p in predicted), "51 (pairing)"
        elif m:
            ok, shown = int(m.group(2)) in predicted, m.group(2)
        else:
            ok, shown = False, vm[:60]
        bad += not ok
        rows.append((r["case"][:-5], shown, ",".join(map(str, predicted)), "ok" if ok else "MISMATCH"))
    width = max(len(x[0]) for x in rows)
    for row in rows:
        if a.verbose or row[3] != "ok":
            print(f"{row[0]:<{width}}  vm={row[1]:<14} spec={row[2]:<10} {row[3]}")
    print(f"{len(rows)} cases, {len(rows) - bad} agree, {bad} mismatch"
          f" ({lock_only} rejected by a Lock outside the spec; pairing not evaluated)")
    return 1 if bad else 0


def lint(a):
    status = 0
    for path in a.specs:
        spec = Spec(path)
        err, warn = spec.lint(a.noir)
        gated = any(w.startswith("generator version 2 will not") for w in warn)
        print(f"{path}: {'FAIL' if err else 'ok'} ({len(spec.actions)} actions, {len(warn)} notes"
              f"{'; specified only, gated on R2' if gated else ''})")
        for e in err:
            print("  error:", e)
        if a.verbose:
            for w in warn:
                print("  note:", w)
        status |= bool(err)
    return status


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lint")
    p.add_argument("specs", nargs="+")
    p.add_argument("--noir", help="Noir main.nr whose public parameter order must match a circuit")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=lint)
    p = sub.add_parser("replay")
    p.add_argument("spec")
    p.add_argument("--cases", required=True, help="directory with results.json and one JSON per case")
    p.add_argument("--pin", action="append", default=[], help="name=0xhex (self, network, vk.<circuit>, ...)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=replay)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()

// R4 spike: in-browser witness solving (backend as wasm) and Groth16 proving (snarkjs).
// For every circuit in circuits/manifest.json: solve the witness and prove RUNS times. After
// each run, outside the timed intervals, compare that run's witness with the one the native
// backend wrote and verify that run's proof. Then check that the verifier rejects the last
// proof with one public input altered. The page reports failure if any check fails;
// measure.cjs exits non-zero on it.
//
// What this page does not check: the file hashes (nothing is pinned; research/browser.md
// section 4), and whether any input leaves the page through storage, logs or the network.
const QUERY = new URLSearchParams(location.search);
const RUNS = Number(QUERY.get("runs") ?? 3);
const ONLY = QUERY.get("only"); // one circuit by name, for devices with little memory
const CHUNK = 65536; // largest buffer crypto.getRandomValues fills in one call
const status = (t) => { document.getElementById("status").textContent = t; };
const timed = async (f) => { const t = performance.now(); const v = await f(); return [v, performance.now() - t]; };
const bytes = async (url) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
};
const median = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
const equal = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

// Randomness for the backend's getrandom hook (lib.rs). Fills in chunks; a thrown exception
// becomes return code 1 instead of escaping the wasm call. Calls are counted per circuit.
const random = { calls: 0, bytes: 0, failures: 0 };
function hostRandom(memory, ptr, len) {
  random.calls += 1;
  random.bytes += len;
  try {
    for (let off = 0; off < len; off += CHUNK) {
      crypto.getRandomValues(new Uint8Array(memory.buffer, ptr + off, Math.min(CHUNK, len - off)));
    }
    return 0;
  } catch (e) {
    random.failures += 1;
    return 1;
  }
}

async function backend() {
  let instance;
  const imports = { env: { host_random: (ptr, len) => hostRandom(instance.exports.memory, ptr, len) } };
  // Fetch, compile and instantiate are timed separately; their sum is the load time.
  const [code, fetchMs] = await timed(() => bytes("backend.wasm"));
  const [module, compileMs] = await timed(() => WebAssembly.compile(code));
  let instantiateMs;
  [instance, instantiateMs] = await timed(() => WebAssembly.instantiate(module, imports));
  const x = instance.exports;
  const put = (data) => { const p = x.alloc(data.length); new Uint8Array(x.memory.buffer, p, data.length).set(data); return p; };
  return {
    bytes: code.length,
    load: { fetchMs, compileMs, instantiateMs },
    selfTest() {
      // The hook on more than one chunk, and on a range outside memory (must return 1, not throw).
      const len = 2 * CHUNK + 1;
      const p = x.alloc(len);
      const view = () => new Uint8Array(x.memory.buffer, p, len);
      view().fill(0);
      const large = hostRandom(x.memory, p, len);
      const lastChunkFilled = view().subarray(2 * CHUNK - 64).some((b) => b !== 0);
      const outside = hostRandom(x.memory, x.memory.buffer.byteLength - 16, 64);
      const result = { bytes: len, status: large, lastChunkFilled, outsideMemoryStatus: outside };
      result.ok = large === 0 && lastChunkFilled && outside === 1;
      Object.assign(random, { calls: 0, bytes: 0, failures: 0 });
      return result;
    },
    witness(artifact, inputs) {
      const code = x.witness(put(artifact), artifact.length, put(inputs), inputs.length);
      const out = new Uint8Array(x.memory.buffer, x.out_ptr(), x.out_len()).slice();
      if (code !== 0) throw new Error(new TextDecoder().decode(out));
      return out;
    },
  };
}

async function circuit(be, c) {
  status(`${c.name}: loading`);
  const dir = `circuits/${c.name}/`;
  const [[artifact, inputs, zkey, reference], fetchMs] = await timed(() => Promise.all(
    ["artifact.json", "inputs.json", "circuit.zkey", "witness.wtns"].map((f) => bytes(dir + f))));
  const vkey = await (await fetch(dir + "vkey.json")).json();
  const row = {
    name: c.name, constraints: c.constraints, zkeyBytes: zkey.length, filesFetchMs: fetchMs,
    witnessMs: [], proveMs: [], witnessEqualsNativeBackend: [], verified: [],
  };
  const before = { ...random };
  let proof, publicSignals;
  for (let i = 0; i < RUNS; i++) {
    status(`${c.name}: run ${i + 1} of ${RUNS}`);
    const [wtns, witnessMs] = await timed(() => be.witness(artifact, inputs));
    let proveMs;
    [{ proof, publicSignals }, proveMs] = await timed(() => snarkjs.groth16.prove(zkey, wtns));
    row.witnessMs.push(witnessMs);
    row.proveMs.push(proveMs);
    // Checks for this run, outside the timed intervals.
    row.witnessEqualsNativeBackend.push(equal(wtns, reference));
    row.verified.push(await snarkjs.groth16.verify(vkey, publicSignals, proof));
  }
  const altered = [...publicSignals];
  altered[0] = (BigInt(altered[0]) + 1n).toString();
  row.rejectsAlteredPublicInput = !(await snarkjs.groth16.verify(vkey, altered, proof));
  row.publicInputs = publicSignals.length;
  row.publicInputsMatchKey = publicSignals.length === vkey.nPublic;
  row.randomCalls = random.calls - before.calls;
  row.randomBytes = random.bytes - before.bytes;
  row.randomFailures = random.failures - before.failures;
  row.witnessMedianMs = Math.round(median(row.witnessMs));
  row.proveFirstMs = Math.round(row.proveMs[0]);
  row.proveMedianMs = Math.round(median(row.proveMs));
  // First use of this circuit once the backend is loaded: its files, one witness, one proof.
  row.firstUseMs = Math.round(fetchMs + row.witnessMs[0] + row.proveMs[0]);
  row.ok = row.witnessEqualsNativeBackend.every(Boolean) && row.verified.every(Boolean)
    && row.rejectsAlteredPublicInput && row.publicInputsMatchKey && row.verified.length === RUNS;
  return row;
}

function render(results) {
  const table = document.getElementById("results");
  const n = (a) => `${a.filter(Boolean).length}/${a.length}`;
  table.innerHTML = "<tr><th>Circuit</th><th>Constraints</th><th>Key (MB)</th><th>Witness, median</th><th>Prove, first</th>"
    + "<th>Prove, median</th><th>Witness equals native</th><th>Verified</th><th>Altered input rejected</th><th>Random calls</th></tr>"
    + results.circuits.map((r) => `<tr><td>${r.name}</td><td>${r.constraints}</td><td>${(r.zkeyBytes / 1e6).toFixed(1)}</td>`
      + `<td>${r.witnessMedianMs}</td><td>${r.proveFirstMs}</td><td>${r.proveMedianMs}</td><td>${n(r.witnessEqualsNativeBackend)}</td>`
      + `<td>${n(r.verified)}</td><td>${r.rejectsAlteredPublicInput}</td><td>${r.randomCalls}</td></tr>`).join("");
}

async function main(results) {
  const manifest = (await (await fetch("circuits/manifest.json")).json()).filter((c) => !ONLY || c.name === ONLY);
  if (manifest.length === 0) throw new Error(`no circuit named ${ONLY}`);
  const be = await backend();
  Object.assign(results, {
    threads: navigator.hardwareConcurrency, runs: RUNS, backendBytes: be.bytes,
    backendFetchMs: Math.round(be.load.fetchMs), backendCompileMs: Math.round(be.load.compileMs),
    backendInstantiateMs: Math.round(be.load.instantiateMs),
    backendLoadMs: Math.round(be.load.fetchMs + be.load.compileMs + be.load.instantiateMs),
    randomSelfTest: be.selfTest(),
  });
  for (const c of manifest) {
    results.circuits.push(await circuit(be, c));
    render(results);
  }
  results.ok = results.randomSelfTest.ok && results.circuits.every((r) => r.ok);
}

const results = { userAgent: navigator.userAgent, circuits: [], ok: false };
main(results)
  .then(() => {
    const failed = results.circuits.filter((r) => !r.ok).map((r) => r.name);
    status(results.ok
      ? `done, every check passed: ${results.threads} threads reported by the browser; backend loaded in ${results.backendLoadMs} ms (fetch ${results.backendFetchMs}, compile ${results.backendCompileMs}, instantiate ${results.backendInstantiateMs})`
      : `FAILED: ${failed.length ? "checks failed for " + failed.join(", ") : "randomness self-test failed"}`);
  })
  .catch((e) => { results.ok = false; results.error = String(e); status("FAILED: " + e.message); })
  .finally(() => { window.__results = results; });

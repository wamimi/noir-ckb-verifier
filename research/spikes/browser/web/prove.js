// R4 spike: in-browser witness solving (backend as wasm) and Groth16 proving (snarkjs).
// For every circuit in circuits/manifest.json: solve, compare the witness with the one the
// native backend wrote, prove RUNS times, verify, and report times.
const QUERY = new URLSearchParams(location.search);
const RUNS = Number(QUERY.get("runs") ?? 3);
const ONLY = QUERY.get("only"); // one circuit by name, for devices with little memory
const status = (t) => { document.getElementById("status").textContent = t; };
const bytes = async (url) => new Uint8Array(await (await fetch(url)).arrayBuffer());
const median = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];

async function backend() {
  let instance;
  const imports = { env: { host_random: (ptr, len) => crypto.getRandomValues(new Uint8Array(instance.exports.memory.buffer, ptr, len)) } };
  const t0 = performance.now();
  ({ instance } = await WebAssembly.instantiateStreaming(fetch("backend.wasm"), imports));
  const x = instance.exports;
  const put = (data) => { const p = x.alloc(data.length); new Uint8Array(x.memory.buffer, p, data.length).set(data); return p; };
  return {
    loadMs: performance.now() - t0,
    witness(artifact, inputs) {
      const status = x.witness(put(artifact), artifact.length, put(inputs), inputs.length);
      const out = new Uint8Array(x.memory.buffer, x.out_ptr(), x.out_len()).slice();
      if (status !== 0) throw new Error(new TextDecoder().decode(out));
      return out;
    },
  };
}

async function main() {
  const manifest = (await (await fetch("circuits/manifest.json")).json()).filter((c) => !ONLY || c.name === ONLY);
  const be = await backend();
  const results = { userAgent: navigator.userAgent, threads: navigator.hardwareConcurrency, backendLoadMs: Math.round(be.loadMs), runs: RUNS, circuits: [] };
  for (const c of manifest) {
    status(`${c.name}: loading`);
    const dir = `circuits/${c.name}/`;
    const [artifact, inputs, zkey, reference] = await Promise.all(
      ["artifact.json", "inputs.json", "circuit.zkey", "witness.wtns"].map((f) => bytes(dir + f)));
    const vkey = await (await fetch(dir + "vkey.json")).json();
    const row = { name: c.name, constraints: c.constraints, zkeyBytes: zkey.length, witnessMs: [], proveMs: [] };
    let wtns, proof, publicSignals;
    for (let i = 0; i < RUNS; i++) {
      status(`${c.name}: run ${i + 1} of ${RUNS}`);
      let t = performance.now();
      wtns = be.witness(artifact, inputs);
      row.witnessMs.push(performance.now() - t);
      t = performance.now();
      ({ proof, publicSignals } = await snarkjs.groth16.prove(zkey, wtns));
      row.proveMs.push(performance.now() - t);
    }
    row.witnessEqualsNativeBackend = wtns.length === reference.length && wtns.every((b, i) => b === reference[i]);
    row.verified = await snarkjs.groth16.verify(vkey, publicSignals, proof);
    row.publicInputs = publicSignals.length;
    row.witnessMedianMs = Math.round(median(row.witnessMs));
    row.proveFirstMs = Math.round(row.proveMs[0]);
    row.proveMedianMs = Math.round(median(row.proveMs));
    results.circuits.push(row);
  }
  const table = document.getElementById("results");
  table.innerHTML = "<tr><th>Circuit</th><th>Constraints</th><th>Key (MB)</th><th>Witness, median</th><th>Prove, first</th><th>Prove, median</th><th>Witness equals native</th><th>Verified</th></tr>"
    + results.circuits.map((r) => `<tr><td>${r.name}</td><td>${r.constraints}</td><td>${(r.zkeyBytes / 1e6).toFixed(1)}</td><td>${r.witnessMedianMs}</td><td>${r.proveFirstMs}</td><td>${r.proveMedianMs}</td><td>${r.witnessEqualsNativeBackend}</td><td>${r.verified}</td></tr>`).join("");
  status(`done: ${results.threads} threads reported by the browser; backend wasm loaded in ${results.backendLoadMs} ms`);
  window.__results = results;
}

main().catch((e) => { status("failed: " + e.message); window.__results = { error: String(e) }; });

//! R4 spike: the pinned Noir-Groth16 backend (witness solving and R1CS wire layout) as a
//! wasm32 module, with no JavaScript glue library. Exports a C ABI:
//!
//!   alloc(len) -> ptr                       buffer the host writes inputs into
//!   witness(artifact_ptr, artifact_len, inputs_ptr, inputs_len) -> status
//!       0: `out_ptr()/out_len()` hold an iden3 .wtns file (the witness in R1CS wire
//!          order, ready for snarkjs);  1: they hold a UTF-8 error message
//!   out_ptr() / out_len()
//!
//! The artifact is the JSON written by `nargo compile`; inputs are a JSON object keyed by
//! parameter name, as for `noir-cli interop`.
use acir::{AcirField, FieldElement};
use noir_acir::Artifact;
use noir_r1cs::compile_r1cs_with_witness;
use noir_witness::{generate_witness_with_options, WitnessSolveOptions};
use std::cell::RefCell;

// The dependency tree pulls in `getrandom` 0.4 (through the ECDSA black-box solvers), which
// has no default backend on wasm32-unknown-unknown. Built with
// `--cfg getrandom_backend="custom"`, it calls this function; randomness comes from the
// host (`crypto.getRandomValues`). Witness solving for the circuits used here asks for none.
#[link(wasm_import_module = "env")]
extern "C" {
    fn host_random(ptr: *mut u8, len: usize);
}

#[no_mangle]
unsafe extern "Rust" fn __getrandom_v03_custom(dest: *mut u8, len: usize) -> Result<(), getrandom::Error> {
    host_random(dest, len);
    Ok(())
}

thread_local! {
    static OUT: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
}

#[no_mangle]
pub extern "C" fn alloc(len: usize) -> *mut u8 {
    let mut buf = Vec::<u8>::with_capacity(len);
    let ptr = buf.as_mut_ptr();
    std::mem::forget(buf);
    ptr
}

#[no_mangle]
pub extern "C" fn out_ptr() -> *const u8 {
    OUT.with(|o| o.borrow().as_ptr())
}

#[no_mangle]
pub extern "C" fn out_len() -> usize {
    OUT.with(|o| o.borrow().len())
}

/// BN254 scalar field modulus, little-endian.
const MODULUS_LE: [u8; 32] = [
    0x01, 0x00, 0x00, 0xf0, 0x93, 0xf5, 0xe1, 0x43, 0x91, 0x70, 0xb9, 0x79, 0x48, 0xe8, 0x33, 0x28,
    0x5d, 0x58, 0x81, 0x81, 0xb6, 0x45, 0x50, 0xb8, 0x29, 0xa0, 0x31, 0xe1, 0x72, 0x4e, 0x64, 0x30,
];

/// iden3 .wtns: header section (field size, modulus, count), then the values.
fn wtns(values: &[FieldElement]) -> Vec<u8> {
    let mut out = Vec::with_capacity(76 + 32 * values.len());
    out.extend_from_slice(b"wtns");
    out.extend_from_slice(&1u32.to_le_bytes()); // format version, as the backend's own writer
    out.extend_from_slice(&2u32.to_le_bytes());
    out.extend_from_slice(&1u32.to_le_bytes());
    out.extend_from_slice(&40u64.to_le_bytes());
    out.extend_from_slice(&32u32.to_le_bytes());
    out.extend_from_slice(&MODULUS_LE);
    out.extend_from_slice(&(values.len() as u32).to_le_bytes());
    out.extend_from_slice(&2u32.to_le_bytes());
    out.extend_from_slice(&(32 * values.len() as u64).to_le_bytes());
    for v in values {
        let mut be = v.to_be_bytes();
        be.reverse();
        out.extend_from_slice(&be);
    }
    out
}

fn run(artifact: &[u8], inputs: &[u8]) -> Result<Vec<u8>, String> {
    let artifact = Artifact::from_json_bytes(artifact).map_err(|e| format!("artifact: {e}"))?;
    let inputs: serde_json::Value = serde_json::from_slice(inputs).map_err(|e| format!("inputs: {e}"))?;
    let solved = generate_witness_with_options(&artifact, &inputs, WitnessSolveOptions { pedantic_solving: false })
        .map_err(|e| format!("witness: {e}"))?;
    let system = compile_r1cs_with_witness(&artifact.program, &solved.witness_vector).map_err(|e| format!("r1cs: {e}"))?;
    let wires = system.materialize_witness(&solved.witness_vector).ok_or("witness does not materialize")?;
    Ok(wtns(&wires))
}

/// # Safety
/// The four arguments must describe two buffers obtained from `alloc` and fully written.
#[no_mangle]
pub unsafe extern "C" fn witness(a_ptr: *mut u8, a_len: usize, i_ptr: *mut u8, i_len: usize) -> u32 {
    let artifact = Vec::from_raw_parts(a_ptr, a_len, a_len);
    let inputs = Vec::from_raw_parts(i_ptr, i_len, i_len);
    let (status, bytes) = match run(&artifact, &inputs) {
        Ok(b) => (0, b),
        Err(e) => (1, e.into_bytes()),
    };
    OUT.with(|o| *o.borrow_mut() = bytes);
    status
}

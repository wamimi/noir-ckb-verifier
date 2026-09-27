// Standalone CKB-VM test harness, not an application Lock or Type Script.
use crate::error::Error;
use alloc::{format, vec::Vec};
use ckb_std::syscalls::{current_cycles, debug};
use sp1_verifier::{PlonkError, PlonkVerifier, PLONK_VK_BYTES};

include!("week13_fixture.rs");

pub fn main() -> Result<(), Error> {
    let args = ckb_std::env::argv();
    let case = args
        .last()
        .and_then(|arg| arg.to_str().ok())
        .ok_or(Error::Encoding)?;
    let mut proof = PROOF.to_vec();
    let mut public_values = Vec::new();
    let mut program_vkey = PROGRAM_VKEY;
    let mut verifier_key = PLONK_VK_BYTES.to_vec();

    match case {
        "valid" => {}
        "wrong-program" => {
            // Change one nibble while retaining a canonical 32-byte program hash.
            program_vkey = "0x00e5c18e0c045a455db8eb2bee09cb2db3c87129e0972cc1562ce3c13d6c9c11";
        }
        "wrong-public-values" => public_values.push(1),
        "changed-proof" => {
            // The upstream benchmark identifies this body mutation for a pairing failure.
            proof[484..516].fill(0);
        }
        "truncated-proof" => proof.truncate(99),
        "wrong-verifier-key" => verifier_key[0] ^= 1,
        _ => {
            debug(format!("week13_unknown_case={case}"));
            return Err(Error::Encoding);
        }
    }

    debug(format!(
        "week13_case={case} proof_bytes={} public_values_bytes={} program_vkey={program_vkey}",
        proof.len(),
        public_values.len()
    ));
    let start = current_cycles();
    let result = PlonkVerifier::verify(&proof, &public_values, program_vkey, &verifier_key);
    let cycles = current_cycles() - start;
    let expected = if case == "valid" { "accept" } else { "reject" };

    let (observed, passed) = match result {
        Ok(()) => ("accept", case == "valid"),
        Err(error) => {
            debug(format!("week13_case={case} verifier_error={error:?}"));
            let expected_error = match case {
                "wrong-program" | "wrong-public-values" | "changed-proof" => {
                    matches!(&error, PlonkError::PairingCheckFailed)
                }
                "wrong-verifier-key" => matches!(&error, PlonkError::PlonkVkeyHashMismatch),
                // The nested error type is private in the pinned dependency.
                "truncated-proof" => format!("{error:?}") == "GeneralError(InvalidData)",
                _ => false,
            };
            ("reject", expected_error)
        }
    };
    debug(format!("week13_case={case} verifier_call_cycles={cycles}"));
    if passed {
        debug(format!(
            "week13_case={case} expected={expected} observed={observed} status=passed"
        ));
        Ok(())
    } else {
        debug(format!(
            "week13_case={case} expected={expected} observed={observed} status=failed"
        ));
        Err(Error::Encoding)
    }
}

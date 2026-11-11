//! Spike script: N Groth16 proofs under one verification key in one script run.
//!
//! args = key data hash (32) ‖ mode (1): 0 verifies each proof on its own with
//! `verifier-core`; 1 verifies all of them with one randomized pairing check.
//! WitnessArgs.input_type of the first group input = u32 N, then N × (u32 length ‖
//! Groth16Witness payload).
//!
//! Batch check, for random r_i derived from everything being verified:
//!   Π e(r_i·A_i, B_i) · e(-(Σ r_i)·α, β) · e(-Σ r_i·X_i, γ) · e(-Σ r_i·C_i, δ) = 1
//! where X_i = IC_0 + Σ_j x_ij·IC_j, so Σ r_i·X_i = (Σ r_i)·IC_0 + Σ_j (Σ_i r_i·x_ij)·IC_j.
//! That is N + 3 Miller loops and one final exponentiation. `verifier-core` (ark-groth16)
//! spends 4 Miller loops and 2 final exponentiations per proof: it computes e(α, β) as a
//! pairing of its own.
#![no_std]
#![no_main]
ckb_std::entry!(program_entry);
ckb_std::default_alloc!();
use alloc::{format, vec::Vec};
use ark_bn254::{Bn254, Fr, G1Affine, G1Projective, G2Affine};
use ark_ec::{pairing::Pairing, AffineRepr, CurveGroup};
use ark_ff::{One, PrimeField, Zero};
use ark_groth16::{Proof, VerifyingKey};
use ark_serialize::CanonicalDeserialize;
use ckb_std::{
    ckb_constants::Source,
    error::SysError,
    high_level::*,
    syscalls::{current_cycles, debug},
};

fn run() -> Result<(), i8> {
    let args = load_script().map_err(|_| 40)?.args().raw_data();
    if args.len() != 33 {
        return Err(41);
    }
    let wa = load_witness_args(0, Source::GroupInput).map_err(|_| 48)?;
    let blob = wa.input_type().to_opt().ok_or(48)?.raw_data();
    let mut vk_data = None;
    for i in 0.. {
        match load_cell_data_hash(i, Source::CellDep) {
            Ok(h) if h[..] == args[..32] => vk_data = Some(load_cell_data(i, Source::CellDep).map_err(|_| 50)?),
            Ok(_) => (),
            Err(SysError::IndexOutOfBound) => break,
            Err(_) => return Err(40),
        }
    }
    let vk_wire = wire_decode::decode_vk_to_arkworks(&vk_data.ok_or(50)?).map_err(|_| 50)?;

    // Split the witness into payloads.
    if blob.len() < 4 {
        return Err(48);
    }
    let n = u32::from_le_bytes(blob[..4].try_into().map_err(|_| 48)?) as usize;
    let mut rest = &blob[4..];
    let mut items = Vec::with_capacity(n);
    for _ in 0..n {
        if rest.len() < 4 {
            return Err(48);
        }
        let len = u32::from_le_bytes(rest[..4].try_into().map_err(|_| 48)?) as usize;
        if rest.len() < 4 + len {
            return Err(48);
        }
        items.push(wire_decode::decode_witness_to_arkworks(&rest[4..4 + len]).map_err(|_| 48)?);
        rest = &rest[4 + len..];
    }
    if n == 0 || !rest.is_empty() {
        return Err(48);
    }
    debug(format!("cycles before verification: {}", current_cycles()));

    if args[32] == 0 {
        for (proof, public) in &items {
            verifier_core::verify(&vk_wire, proof, public).map_err(|_| 51)?;
        }
        return Ok(());
    }

    let vk = VerifyingKey::<Bn254>::deserialize_compressed(&vk_wire[..]).map_err(|_| 50)?;
    let inputs = vk.gamma_abc_g1.len() - 1;
    // Randomness: a hash of the key and of every proof and public input in the batch.
    let mut seed = ckb_hash::new_blake2b();
    seed.update(&args[..32]);
    seed.update(&blob);
    let mut seed_bytes = [0u8; 32];
    seed.finalize(&mut seed_bytes);

    let mut g1 = Vec::with_capacity(n + 3);
    let mut g2 = Vec::with_capacity(n + 3);
    let mut sum_r = Fr::zero();
    let mut sum_rx = alloc::vec![Fr::zero(); inputs];
    let mut sum_rc = G1Projective::zero();
    for (i, (proof, public)) in items.iter().enumerate() {
        let proof = Proof::<Bn254>::deserialize_compressed(&proof[..]).map_err(|_| 51)?;
        if proof.a.is_zero() || proof.b.is_zero() || proof.c.is_zero() || public.len() != 4 + 32 * inputs {
            return Err(51);
        }
        let r = if i == 0 {
            Fr::one()
        } else {
            let mut h = ckb_hash::new_blake2b();
            h.update(&seed_bytes);
            h.update(&(i as u32).to_le_bytes());
            let mut out = [0u8; 32];
            h.finalize(&mut out);
            Fr::from_le_bytes_mod_order(&out[..16]) // 128-bit challenge
        };
        sum_r += r;
        for j in 0..inputs {
            let x = Fr::deserialize_compressed(&public[4 + 32 * j..36 + 32 * j]).map_err(|_| 51)?;
            sum_rx[j] += r * x;
        }
        sum_rc += proof.c * r;
        g1.push((proof.a * r).into_affine());
        g2.push(proof.b);
    }
    let mut x = vk.gamma_abc_g1[0] * sum_r;
    for j in 0..inputs {
        x += vk.gamma_abc_g1[j + 1] * sum_rx[j];
    }
    let neg = |p: G1Projective| -> G1Affine { (-p).into_affine() };
    g1.push(neg(vk.alpha_g1 * sum_r));
    g2.push(vk.beta_g2);
    g1.push(neg(x));
    g2.push(vk.gamma_g2);
    g1.push(neg(sum_rc));
    g2.push(vk.delta_g2);
    // Miller loops in chunks of 8 so prepared G2 points never occupy more than a fixed
    // amount of memory; the partial products are multiplied and exponentiated once.
    let mut product = <Bn254 as Pairing>::TargetField::one();
    for (a, b) in g1.chunks(8).zip(g2.chunks(8)) {
        let prepared: Vec<<Bn254 as Pairing>::G2Prepared> = b.iter().map(|p: &G2Affine| (*p).into()).collect();
        product *= Bn254::multi_miller_loop(a.iter().copied(), prepared).0;
    }
    let ok = Bn254::final_exponentiation(ark_ec::pairing::MillerLoopOutput(product)).map(|r| r.0.is_one()).unwrap_or(false);
    debug(format!("cycles after verification: {}", current_cycles()));
    if ok {
        Ok(())
    } else {
        Err(51)
    }
}

pub fn program_entry() -> i8 {
    match run() {
        Ok(()) => 0,
        Err(e) => e,
    }
}

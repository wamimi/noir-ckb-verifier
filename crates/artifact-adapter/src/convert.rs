use std::str::FromStr;

use ark_bn254::{Bn254, Fq, Fq2, Fr, G1Affine, G2Affine};
use ark_ec::AffineRepr;
use ark_ff::{BigInteger, PrimeField};
use ark_groth16::{Groth16, Proof, VerifyingKey};
use ark_snark::SNARK;
use num_bigint::BigUint;

use crate::{
    json::{G1Json, G2Json, SnarkJsProof, SnarkJsVerifyingKey},
    AdapterError,
};

#[derive(Clone, Debug)]
pub struct ConvertedArtifacts {
    pub verifying_key: VerifyingKey<Bn254>,
    pub proof: Proof<Bn254>,
    pub public_inputs: Vec<Fr>,
}

fn validate_protocol_curve(protocol: &str, curve: &str) -> Result<(), AdapterError> {
    if protocol != "groth16" {
        return Err(AdapterError::UnsupportedProtocol(protocol.to_owned()));
    }
    if curve != "bn128" {
        return Err(AdapterError::UnsupportedCurve(curve.to_owned()));
    }
    Ok(())
}

fn parse_canonical_uint(value: &str, label: &str) -> Result<BigUint, AdapterError> {
    let canonical = value == "0"
        || (!value.is_empty()
            && !value.starts_with('0')
            && value.as_bytes().iter().all(u8::is_ascii_digit));
    if !canonical {
        return Err(AdapterError::InvalidDecimal {
            label: label.to_owned(),
            value: value.to_owned(),
        });
    }
    BigUint::parse_bytes(value.as_bytes(), 10).ok_or_else(|| AdapterError::InvalidDecimal {
        label: label.to_owned(),
        value: value.to_owned(),
    })
}

fn modulus_biguint<F: PrimeField>() -> BigUint {
    BigUint::from_bytes_le(&F::MODULUS.to_bytes_le())
}

fn parse_fq(value: &str, label: &str) -> Result<Fq, AdapterError> {
    let integer = parse_canonical_uint(value, label)?;
    if integer >= modulus_biguint::<Fq>() {
        return Err(AdapterError::FieldOutOfRange {
            label: label.to_owned(),
            field: "BN254 base",
        });
    }
    Fq::from_str(value).map_err(|_| AdapterError::InvalidDecimal {
        label: label.to_owned(),
        value: value.to_owned(),
    })
}

fn parse_fr(value: &str, label: &str) -> Result<Fr, AdapterError> {
    let integer = parse_canonical_uint(value, label)?;
    if integer >= modulus_biguint::<Fr>() {
        return Err(AdapterError::FieldOutOfRange {
            label: label.to_owned(),
            field: "BN254 scalar",
        });
    }
    Fr::from_str(value).map_err(|_| AdapterError::InvalidDecimal {
        label: label.to_owned(),
        value: value.to_owned(),
    })
}

fn expect_g1_affine_marker(point: &G1Json, label: &str) -> Result<(), AdapterError> {
    if point[2] != "1" {
        return Err(AdapterError::ProjectiveMarker {
            label: format!("{label}.z"),
            observed: point[2].clone(),
            expected: "1",
        });
    }
    Ok(())
}

fn expect_g2_affine_marker(point: &G2Json, label: &str) -> Result<(), AdapterError> {
    if point[2][0] != "1" || point[2][1] != "0" {
        return Err(AdapterError::ProjectiveMarker {
            label: format!("{label}.z"),
            observed: format!("[{},{}]", point[2][0], point[2][1]),
            expected: "[1,0]",
        });
    }
    Ok(())
}

fn parse_g1(point: &G1Json, label: &str) -> Result<G1Affine, AdapterError> {
    expect_g1_affine_marker(point, label)?;
    let candidate = G1Affine::new_unchecked(
        parse_fq(&point[0], &format!("{label}.x"))?,
        parse_fq(&point[1], &format!("{label}.y"))?,
    );
    if candidate.is_zero() {
        return Err(AdapterError::PointAtInfinity {
            label: label.to_owned(),
        });
    }
    if !candidate.is_on_curve() {
        return Err(AdapterError::PointNotOnCurve {
            label: label.to_owned(),
        });
    }
    if !candidate.is_in_correct_subgroup_assuming_on_curve() {
        return Err(AdapterError::PointWrongSubgroup {
            label: label.to_owned(),
        });
    }
    Ok(candidate)
}

fn parse_fq2(value: &[String; 2], label: &str) -> Result<Fq2, AdapterError> {
    // ffjavascript/snarkjs represents Fq2 as [c0, c1]. arkworks Fq2::new
    // takes the same semantic coefficient order. Solidity calldata reverses
    // these coefficients for the EVM precompile; this adapter does not.
    Ok(Fq2::new(
        parse_fq(&value[0], &format!("{label}.c0"))?,
        parse_fq(&value[1], &format!("{label}.c1"))?,
    ))
}

fn parse_g2(point: &G2Json, label: &str) -> Result<G2Affine, AdapterError> {
    expect_g2_affine_marker(point, label)?;
    let candidate = G2Affine::new_unchecked(
        parse_fq2(&point[0], &format!("{label}.x"))?,
        parse_fq2(&point[1], &format!("{label}.y"))?,
    );
    if candidate.is_zero() {
        return Err(AdapterError::PointAtInfinity {
            label: label.to_owned(),
        });
    }
    if !candidate.is_on_curve() {
        return Err(AdapterError::PointNotOnCurve {
            label: label.to_owned(),
        });
    }
    if !candidate.is_in_correct_subgroup_assuming_on_curve() {
        return Err(AdapterError::PointWrongSubgroup {
            label: label.to_owned(),
        });
    }
    Ok(candidate)
}

pub fn convert_public_inputs(values: &[String]) -> Result<Vec<Fr>, AdapterError> {
    values
        .iter()
        .enumerate()
        .map(|(index, value)| parse_fr(value, &format!("public[{index}]")))
        .collect()
}

pub fn convert(
    vk: &SnarkJsVerifyingKey,
    proof: &SnarkJsProof,
    public_values: &[String],
) -> Result<ConvertedArtifacts, AdapterError> {
    validate_protocol_curve(&vk.protocol, &vk.curve)?;
    validate_protocol_curve(&proof.protocol, &proof.curve)?;

    if vk.n_public != public_values.len() || vk.ic.len() != public_values.len() + 1 {
        return Err(AdapterError::PublicInputCount {
            declared: vk.n_public,
            supplied: public_values.len(),
            ic_entries: vk.ic.len(),
        });
    }

    let verifying_key = VerifyingKey {
        alpha_g1: parse_g1(&vk.vk_alpha_1, "vk.vk_alpha_1")?,
        beta_g2: parse_g2(&vk.vk_beta_2, "vk.vk_beta_2")?,
        gamma_g2: parse_g2(&vk.vk_gamma_2, "vk.vk_gamma_2")?,
        delta_g2: parse_g2(&vk.vk_delta_2, "vk.vk_delta_2")?,
        gamma_abc_g1: vk
            .ic
            .iter()
            .enumerate()
            .map(|(index, point)| parse_g1(point, &format!("vk.IC[{index}]")))
            .collect::<Result<_, _>>()?,
    };

    let proof = Proof {
        a: parse_g1(&proof.pi_a, "proof.pi_a")?,
        b: parse_g2(&proof.pi_b, "proof.pi_b")?,
        c: parse_g1(&proof.pi_c, "proof.pi_c")?,
    };

    Ok(ConvertedArtifacts {
        verifying_key,
        proof,
        public_inputs: convert_public_inputs(public_values)?,
    })
}

pub fn verify(
    verifying_key: &VerifyingKey<Bn254>,
    public_inputs: &[Fr],
    proof: &Proof<Bn254>,
) -> Result<bool, AdapterError> {
    Groth16::<Bn254>::verify(verifying_key, public_inputs, proof)
        .map_err(|_| AdapterError::VerificationFailed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scalar_parser_rejects_modulus_instead_of_reducing_it() {
        let modulus = Fr::MODULUS.to_string();
        assert!(matches!(
            parse_fr(&modulus, "test"),
            Err(AdapterError::FieldOutOfRange { .. })
        ));
    }

    #[test]
    fn scalar_parser_rejects_noncanonical_decimal_text() {
        assert!(matches!(
            parse_fr("049", "test"),
            Err(AdapterError::InvalidDecimal { .. })
        ));
    }

    #[test]
    fn point_parser_rejects_non_affine_marker() {
        let point = ["1".to_owned(), "2".to_owned(), "0".to_owned()];
        assert!(matches!(
            parse_g1(&point, "test"),
            Err(AdapterError::ProjectiveMarker { .. })
        ));
    }

    #[test]
    fn point_parser_rejects_off_curve_coordinates() {
        let point = ["0".to_owned(), "0".to_owned(), "1".to_owned()];
        assert!(matches!(
            parse_g1(&point, "test"),
            Err(AdapterError::PointNotOnCurve { .. })
        ));
    }
}

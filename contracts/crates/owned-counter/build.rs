use std::{env, fs, path::PathBuf};
fn main() {
    let mut source = String::new();
    for name in [
        "NETWORK_DOMAIN",
        "OWNER_CODE_HASH",
        "OWNER_DATA_HASH",
        "VK_DATA_HASH",
    ] {
        let key = format!("COUNTER_{name}");
        println!("cargo:rerun-if-env-changed={key}");
        let value = env::var(&key).unwrap_or_else(|_| panic!("missing pinned build value {key}"));
        let value = value.strip_prefix("0x").unwrap_or(&value);
        assert_eq!(value.len(), 64, "{key} must be 32-byte hex");
        let bytes: Vec<u8> = (0..64)
            .step_by(2)
            .map(|i| u8::from_str_radix(&value[i..i + 2], 16).expect("hex"))
            .collect();
        assert!(bytes.iter().any(|b| *b != 0), "zero policy pin forbidden");
        source.push_str(&format!("const {name}: [u8;32] = {bytes:?};\n"));
    }
    fs::write(
        PathBuf::from(env::var_os("OUT_DIR").unwrap()).join("policy.rs"),
        source,
    )
    .unwrap();
}

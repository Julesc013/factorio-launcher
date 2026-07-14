# Validation evidence

- Universal Setup exact-main CI `29355175219`: PASS on Linux, macOS, Windows,
  sanitizer, and bounded fuzz lanes.
- Universal Setup local proof: 16/16 native and 21/21 Python PASS.
- FacMan Release CTest: 41/41 PASS.
- FacMan complete Python discovery: 343 PASS in 428.384 seconds with one
  unchanged opt-in bounded-scale performance skip.
- Focused resolver remediation: 14/14 PASS.
- Strict validation and schema validation over 230 schemas: PASS.
- Required Windows package proof: 14/14 PASS, zero skips.
- Clean selected-package reproducibility at
  `eff0f9146e6a28fcee484f72d7d2d7e691bade92`: PASS over 395 files.
- Package tree:
  `92c0be8a0772aac4035cdc70a21d8c0da27f6b6b5d1ecc8142176e73cd29794f`.
- Archive:
  `f278288bb1dd8f184012b1bf994bac8e90a996c2c3b17ad15f04a9c20373e230`.
- SBOM:
  `26bc19c088b8e56cf1171efb78e236e816a30a14731870e5261b102c57d7fe15`.
- Provenance:
  `4425484c2a7d99e08eb39ba8fe0093f5cc094c0d1fa1fdd98cc812a9740e7aad`.
- Every WU9 commit message was checked against the structured AIDE policy.

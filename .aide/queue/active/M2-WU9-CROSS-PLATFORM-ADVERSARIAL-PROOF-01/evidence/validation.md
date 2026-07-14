# Validation evidence

- Universal Setup exact-main CI `29355175219`: PASS on Linux, macOS, Windows,
  sanitizer, and bounded fuzz lanes.
- Universal Setup local proof: 16/16 native and 21/21 Python PASS.
- FacMan Release CTest: 41/41 PASS.
- FacMan complete post-remediation Python discovery: 344 PASS in 393.762 seconds with one
  unchanged opt-in bounded-scale performance skip.
- Focused resolver remediation: 14/14 PASS.
- Strict validation and schema validation over 230 schemas: PASS.
- Required Windows package proof: 14/14 PASS, zero skips.
- Clean selected-package reproducibility at
  `77a39becc55109240abd3ee38227ded666a883fe`: PASS over 395 files.
- Package tree:
  `32c76b89269266733896d9a29879f553111bda79b37fa88b2a14c69bb5aca18f`.
- Archive:
  `191cf5fc1d224bc74ac707ebff715e5166401eed9270a8c29268c2774beeb5dc`.
- SBOM:
  `bdae09c3c822f13cf468b950280eca082a2c74871029e302cd032fd11c1008f3`.
- Provenance:
  `ca04bbf34554b8ed66a15ad9d66d822bd9a7826e6b41066cd1eb97e08a626713`.
- Initial push CI `29358809851` and PR CI `29358824982`: Windows-only
  manifest checkout-identity failure; all other platform/analysis lanes PASS.
- LF/CRLF remediation focused suite: 8/8 PASS; replacement hosted runs PASS.
- Replacement task push CI `29360424668`, CodeQL `29360424648`, and security
  `29360424632`: PASS.
- Replacement PR CI `29360426297`, CodeQL `29360426365`, security
  `29360426450`, and schema `29360426425`: PASS.
- Exact-`dev` CI `29361218441`, CodeQL `29361218988`, security `29361218569`,
  and schema `29361219348`: PASS.
- Every WU9 commit message was checked against the structured AIDE policy.

<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

- Exact-pin Release build and CTest: 41/41 PASS.
- Complete Python discovery: 339 PASS, one unchanged opt-in skip.
- Full strict validation: PASS.
- AIDE Lite test: PASS.
- Required Windows package proof: 14/14 PASS, zero skips.
- Selected package reproducibility: PASS over 390 files; archive
  `965c3588fb9ead5cf826f3489b7c09f7b32e6f1a1e2a7f38bebb216054919fb2`,
  tree `5df6d578c8a1054a9d24f8bc0641c692f8420ee062901177546b1fa0692fae25`,
  SBOM `e684549e9d0f861c4188114eb8b707864b5015d0a30a1d9f66e33d6c3e47d40f`,
  provenance `39235fb79ad15afb8350d20368b1e2cb3e96fd28219ebca432741a3a9f2daefc`.
- WU6 exact-dev CI `29344174316`, CodeQL `29344174402`, and security
  `29344174517`: PASS and bound before WU7 closeout.

Hosted WU7 integration remains required after review.

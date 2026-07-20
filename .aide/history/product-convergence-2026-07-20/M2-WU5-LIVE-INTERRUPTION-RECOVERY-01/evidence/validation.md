<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

- Universal Setup 16/16 Release CTest: PASS.
- Universal Setup 21/21 Python tests and strict check: PASS.
- Provider PR #16 push CI `29337549251`: PASS.
- Provider PR #16 pull-request CI `29337549896`: PASS.
- Provider exact-main CI `29337717932`: PASS.
- Retained acceptance summary SHA-256
  `c64ddfaa38bde351002d2840999b3ba74173cde8c76d3e6aa21891b5d169f6c1`:
  independently recomputed.
- Combined exact-pin FacMan/Launcher/Setup Release CTest: 40/40 PASS.
- Complete FacMan Python suite: 339 PASS, one opt-in skip.
- FacMan strict and AIDE portable validation: PASS.
- Required Windows package proof: 14/14 PASS, zero skips.
- Selected package reproducibility: PASS over 389 files; archive
  `42156c1a2f37f5fc5e9df6a487b593902e3f98e349ed2cfd386a674099136903`,
  tree `28b275dfab572293755291d15f84598cb24f03675a202be2ee621c56c03a6e7c`,
  SBOM `f63be981fb9cad5f72760905b7bec66afe8c624cff0134a3e6f8780429e62414`,
  provenance `b4e8fd67ac3e255278eed4a10dcb2504b4ae21d9fd17c0476d6b7c1b3cedef86`.

Hosted FacMan integration proof remains required after review. Automation has
not created the human verdict.

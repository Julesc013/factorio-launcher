<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

- Universal Setup 15/15 Release CTest: PASS;
- Universal Setup 21/21 Python tests: PASS;
- Universal Setup strict policy: PASS;
- provider PR #15 push CI `29334554537`: PASS;
- provider PR #15 pull-request CI `29334556981`: PASS;
- provider exact-main CI `29334632894`: PASS;
- retained run summary hash and all packet/journal/audit/state identities:
  independently re-read and bound;
- final current moved root absent, pre-move root retained, setup state and
  source archive retained: PASS.
- combined FacMan/Launcher/Setup Release CTest: 39/39 PASS;
- complete Python suite: 339 PASS, one opt-in skip;
- strict and AIDE portable validation: PASS;
- required Windows package proof: 14/14 PASS, zero skips;
- selected package reproducibility: PASS over 388 files, archive
  `9a26fa612773108ae4e2f2f1762f9561df3f850459065abdfc2f9e608bc1ca55`,
  tree `4dcf73452223cede21d24a74b5637289dc8b1509e1e72957f8f7f13d61389195`,
  SBOM `1589f6c625a3580fc5264e887f5260917bd428124573cac060c35aae1c975f82`,
  provenance `a9be745af843b98b30cedd72f0359f131c98f87f1d5ddc190a19f717f30771c4`.

The result is automated lifecycle proof only. Operator verdict remains
`pending`.

<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

- Universal Launcher exact-main CI `29337737777`: PASS.
- Focused exact-pin FacMan/Launcher tests: 6/6 PASS.
- FacMan strict validation: PASS.
- Complete combined native proof: 41/41 PASS.
- Complete Python proof: 339 PASS, one unchanged opt-in skip.
- Required Windows package proof: 14/14 PASS, zero skips.
- Selected 390-file package reproducibility: PASS; archive
  `3a50263dde4871efc042d9289bef78b7abd6c364719b74ef18c91b8247c62fa8`,
  tree `c71458a16c201bf03fcd988795d44cc18564c63e7ef9c35b79dda108dcdaf470`,
  SBOM `0f35b6be81e81fedcc2e12268c8192f752eca4f283d54856d604e3a916ffa722`,
  provenance `0a5f36d9c637d20d9cb9139d94438a4d73efff27cc969f4b88829c7a15bd78c1`.
- WU5 exact-`dev` CI `29341098765`, CodeQL `29341101347`, and security
  policy `29341100659`: PASS.
- WU6 hosted integration remains pending for WorkUnit closeout.

The focused proof covers a recovery-required install before an install
reference exists, the stable `managed_install_recovery_required` status, stale
launch-plan projection, additive ABI compatibility, installed SDK consumption,
and the preserved Launcher no-mutation authority boundary.

<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

- Exact-pin Release build and CTest: 41/41 PASS.
- Complete Python discovery: 339 PASS, one unchanged opt-in skip.
- Full strict validation: PASS.
- AIDE Lite test: PASS.
- Required Windows package proof: 14/14 PASS, zero skips.
- Selected package reproducibility: PASS at source revision
  `0e50b6fe0e90707926bf71940db6507aa8580a80` over 391 files; archive
  `8899dec862a6dd2558603e8be3a47ebd7380e7eae77f58e892cb8226630576e0`,
  tree `ae2b34f3ed610a4bdde3228e6452343b9b32e3993bb6d057f6f01c5fed761bb6`,
  SBOM `7aa4fb5be301133a2611918bf9bad842642da931140cc46543bd25f2ccacb671`,
  provenance `ebb7d31f17babec6f6949fa86e24026eb5da6841bb472151abd79f1b8225c960`.
- WU6 exact-dev CI `29344174316`, CodeQL `29344174402`, and security
  `29344174517`: PASS and bound before WU7 closeout.

Hosted WU7 integration remains required after review.

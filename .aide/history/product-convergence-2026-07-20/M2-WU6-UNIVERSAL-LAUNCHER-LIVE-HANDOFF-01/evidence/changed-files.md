<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Changed Files

- Advanced Universal Launcher to canonical main `7bd4425f0c35414f738159b45d8bec42edf70235`.
- Raised the additive FacMan/Launcher ABI contract from 1.2 to 1.3 while
  retaining compatibility with earlier 1.x consumers.
- Added a FacMan-owned recovery-required projection smoke test.
- Refreshed dependency locks, SBOM identity, notices, runtime status, provider
  pin validation, installed-consumer checks, project truth, and checkpoint.

The change does not route setup mutation through Universal Launcher.

<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

## Provider exact-main evidence

- Universal Launcher `6d41e07b76cd19b2a7630835e05ac3aa125d57b8`: CI run
  `29311615251` passed.
- Universal Setup `264bb1939a67231878313155157abd0f83d24c13`: CI run
  `29311599523` passed.
- Both canonical `LICENSE` blobs have SHA-256
  `fb32a9968f4a0e33e1e2f367ebe81f0d1703fd38b2e473d9e300f4efd8292b53`.

## Clean three-repository reconstruction

`py -3 tools/repro_workspace_smoke.py --build --require-clean --build-root
build/m1-license-final-repro-4` passed from an empty root:

- Universal Launcher configure, build, CTest, and strict: PASS;
- Universal Setup configure, build, CTest, and strict: PASS;
- FacMan configure, build, 35/35 CTest, AIDE, strict, and Python corpus: PASS.

## Selected-package reproducibility

Two independent `windows_portable_cli_x64` builds were byte-identical:

| Evidence | Identity |
| --- | --- |
| archive | 1,912,841 bytes; `993bf60ddd4332abdab1950d3df4220235314dac959806a1c2fa3dbf80267706` |
| package tree | 383 files; `81eab95e8cf0731932723e8a96ea75ad80c9a6f72502a78c54a60f8227031f44` |
| SPDX 2.3 SBOM | 6,220 bytes; `9b1939cb56f3e735c0bba733190f7f4dea827c8e95dd5868b7bf6eb26c53c872` |
| adjacent provenance | 2,088 bytes; `52a2e9fd637d78609671cff2baba3adbb7f063068c9a0b8d2e355ff39d58f03d` |

The report recorded `source_dirty = false`, exact source revisions, publisher
authenticity not proven, execution unchanged/not authorized, and no H1 inference.

## Focused remediation

- Long-root transaction session that originally failed: PASS.
- Explicit greater-than-260-character durable Windows I/O regression: PASS.
- Package runtime matrix: 27/27 PASS.
- AIDE Lite validation: PASS.
- Full strict validation: PASS.

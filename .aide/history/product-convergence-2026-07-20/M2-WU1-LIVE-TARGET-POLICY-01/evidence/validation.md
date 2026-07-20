<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

## Universal Setup exact repository evidence

| Identity | Value |
| --- | --- |
| task head | `804ae1ea2f9fdb78525a0a3ef09069b51d8bb1c1` |
| canonical `main` merge | `f322655fa8fa287a400f7afb6c661eade30d707b` |
| push CI | `29316580182` |
| PR CI | `29316591892` |
| exact-main CI | `29316660078` |

Every run passed test, sanitizer, and 1,000-iteration bounded fuzz jobs. Local
validation passed 11/11 native tests, 19/19 Python tests, structure, language
runtime, and MIT license checks. The native policy smoke covers every accepted
class/activation combination and all thirteen refusal branches.

## FacMan provider and package proof

- provider integration revision: `dfa0d8ad3c4cf5634896a67f9908ef8a5a922983`;
- 36/36 integrated native tests passed, including the Universal Setup policy
  smoke and the installed SDK consumer;
- 20/20 focused Python contract, state, refusal, schema, and strict cases
  passed;
- AIDE Lite, compliance, dependency/workspace lock, generated state, and full
  strict validation passed;
- required Windows package proof passed 14/14 with zero skips.

Two independent `windows_portable_cli_x64` packages were byte-identical:

| Evidence | Identity |
| --- | --- |
| archive | 1,915,237 bytes; `2410caa6a626f16305b64a79652d9b29ef5adebb17bd4a74ec4c188e40899446` |
| package tree | 384 files; `58be84a38006324da84b129239a5aefe2608ac2074a8e37cb91a119e0988f4d1` |
| SPDX 2.3 SBOM | 6,220 bytes; `7e78664f5965ba933b5b7aa3096fde8738c492b0dcfbbeb60f68795e0d911ba3` |
| adjacent provenance | 2,088 bytes; `8d3bf8692a00c9a2b20b0cd3034d2ee77697e229dc22c16e3d7665d2d89de80e` |

The report records clean sources at FacMan `dfa0d8a`, Universal Launcher
`6d41e07`, and Universal Setup `f322655`; publisher authenticity remains
unproven, execution is unchanged/unavailable, and no H1 inference is made.

The complete hosted FacMan corpus remains a promotion-PR gate. A local full
discovery run exceeded the command wrapper limit and is not counted as a Pass;
no test failure was reported before termination.

<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

## Exact provider evidence

| Evidence | Identity |
| --- | --- |
| Universal Setup WU2 task | `9baacd5547ddd7fe2705d3749059f7cb22a86e38` |
| Universal Setup capacity remediation | `1ac39871120364ba554a8831d0d0860e2078ad35` |
| Universal Setup canonical `main` | `aa4d8cec93f265893f246d217ee94c03073899a3` |
| Provider push / PR / main CI | `29322088318` / `29322092513` / `29322161463` |
| Universal Launcher retained provider | `6d41e07b76cd19b2a7630835e05ac3aa125d57b8` |
| FacMan provider integration | `d16e71357f13382c43b68b8de99bbd8758d97c8b` |
| FacMan validation remediation | `316ee8efec5b962e6c2ed8419c0453c0c6062654` |

The final Universal Setup run passed its test, sanitizer, and bounded-fuzz
jobs. Local provider proof passed 13 native tests, 20 Python tests, and strict
validation.

## Clean three-repository reconstruction

`py -3 tools/repro_workspace_smoke.py --build --require-clean --build-root
build/m2-wu2-repro-clean-4` passed from an initially empty proof root at FacMan
`d16e71357f13382c43b68b8de99bbd8758d97c8b`:

- Universal Launcher configure, build, CTest, and strict: PASS;
- Universal Setup configure, build, CTest, and strict: PASS;
- FacMan configure, build, CTest, AIDE Lite, strict, and Python: PASS.

The first capture wrapper reached its ten-minute ceiling while the healthy
Python child continued and completed. That detached run is not accepted. The
same proof root was rerun with a sufficient capture window and returned exit
zero after 416.5 seconds.

## Final FacMan validation

- integrated native CTest: 38/38 PASS;
- Python discovery: 339 cases PASS with one intentional opt-in skip;
- required Windows package proof: 14/14 PASS with zero skips;
- complete strict validation: PASS;
- AIDE Lite validation and structured commit checks: PASS;
- package hash closure and relocated runtime smoke: PASS.

Two raw Python runs against a legacy `build/Debug/facman.exe` failed with 12
provider/command-graph mismatches and are not accepted. Commit `316ee8e`
remediates the ambiguous test selector, adds a regression, and the no-override
339-case rerun passes against canonical `build/native-smoke`.

An initial package runtime command used a workspace below the source checkout;
the smoke correctly rejected the echoed requested path. The corrected external
temporary-workspace invocation passed and is the accepted relocation result.

## Selected-package reproducibility

Two independent `windows_portable_cli_x64` packages built from clean sources
at FacMan `316ee8e`, Launcher `6d41e07`, and Setup `aa4d8ce` were byte
identical:

| Evidence | Identity |
| --- | --- |
| archive | 1,384,569 bytes; `355c2ef881c97f65d1c630eb7c62809caa657934196bd328be7bebc121d6762c` |
| package tree | 385 files; `c5a970504e9c33462db313bfa63be7b0d3f2a1d8a8994bc5220ce5224027edd2` |
| SPDX 2.3 SBOM | 6,220 bytes; `2279534491de1a27b028f55cd9b470c40705eea1c2c642f3f2c6a1bf35f9ef72` |
| adjacent provenance | 2,088 bytes; `adf4b71a66cef4e7c1b7d9adfa6eaae2bcac5b8e39fd5228eb2f83cbbfbcd4f6` |

The report records `source_dirty = false`, unsigned/unpublished authenticity,
unchanged execution authority, and no H1 inference.

## Authority result

This is an implementation proof pending FacMan `dev` integration. Automation
did not produce an M2 human verdict. Ordinary managed-portable apply and real
Factorio archive acceptance remain unavailable. `recovery.apply` remains
unavailable until the durable WU5 recovery proof exists.

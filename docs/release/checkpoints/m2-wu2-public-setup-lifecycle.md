<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU2 Public Setup Lifecycle

Status: accepted `dev` integration proof; human acceptance pending.

This checkpoint records the bounded activation of Universal Setup's already
fixture-proven lifecycle through explicit descriptor-driven public commands.
It does not record an operator live-target Pass, promote ordinary managed
portable apply, accept a real Factorio archive, or authorize execution.

## Bound identities

| Repository/evidence | Identity |
| --- | --- |
| Universal Setup WU2 task | `9baacd5547ddd7fe2705d3749059f7cb22a86e38` |
| Universal Setup remediation | `1ac39871120364ba554a8831d0d0860e2078ad35` |
| Universal Setup canonical `main` | `aa4d8cec93f265893f246d217ee94c03073899a3` |
| Universal Setup push / PR / main CI | `29322088318` / `29322092513` / `29322161463` |
| Universal Launcher retained provider | `6d41e07b76cd19b2a7630835e05ac3aa125d57b8` |
| FacMan provider integration | `d16e71357f13382c43b68b8de99bbd8758d97c8b` |
| FacMan validation remediation | `316ee8efec5b962e6c2ed8419c0453c0c6062654` |
| FacMan reviewed PR head | `f051731b80b51cac2d192ddb39535485f2a9c431` |
| FacMan preserved `dev` merge | `747b4442cf228561de9fa15834bf78b0dad72f23` |
| FacMan exact-`dev` CI / CodeQL / security | `29326004461` / `29326004230` / `29326004219` |

## Public command law

The Setup provider exposes explicit install inspect/plan/apply,
installed-state inspect/verify, repair plan/apply, move plan/apply, uninstall
plan/apply, and recovery inspect/plan descriptors. Plan commands do not
initialize writable state. Apply requires `APPLY`, the reviewed plan identity,
and immediate reconstruction and revalidation of every bound input.

Pre-verdict mutation remains limited to `operator_acceptance` below the exact
configured acceptance root. Existing targets are not merged or overwritten;
repair and uninstall use recorded owned state; uninstall refuses before any
deletion when foreign or changed content is present.

`recovery.apply` is deliberately unavailable. WU5 must first prove a durable
restart-safe staged-file closure rather than inferring recovery authority from
inspect/plan behavior.

## Proof result

- Universal Setup exact-main CI passed test, sanitizer, and bounded fuzz jobs;
- clean three-repository reconstruction passed every build, CTest, strict,
  AIDE, installed-consumer, and Python gate;
- FacMan passed 38/38 native tests and 339 Python cases with one opt-in skip;
- the required Windows package proof passed 14/14 with zero skips;
- a 385-file selected package was byte-identical across independent roots.

| Reproducible evidence | SHA-256 |
| --- | --- |
| archive | `355c2ef881c97f65d1c630eb7c62809caa657934196bd328be7bebc121d6762c` |
| package tree | `c5a970504e9c33462db313bfa63be7b0d3f2a1d8a8994bc5220ce5224027edd2` |
| SBOM | `2279534491de1a27b028f55cd9b470c40705eea1c2c642f3f2c6a1bf35f9ef72` |
| provenance | `adf4b71a66cef4e7c1b7d9adfa6eaae2bcac5b8e39fd5228eb2f83cbbfbcd4f6` |

Publisher authenticity remains unproven and the artifact remains unsigned and
unpublished.

The exact-`dev` CI run passed Linux, Windows, macOS, coverage, sanitizer,
bounded-fuzz, package, reproducibility, WinForms, TUI, AppKit compile, and
archive jobs. Exact-`dev` CodeQL passed C/C++, C#, and Python; security policy
also passed. These workflows prove integration, not operator acceptance.

## Authority retained

- The human M2 verdict is `pending`; automation did not create it.
- Ordinary live-target apply and real Factorio archive acceptance are
  unavailable.
- No existing `D:\Games\Factorio` or Steam state was touched.
- Network, credentials, registry, shortcuts, elevation, package-manager,
  installer, process execution, signing, and publication remain unavailable.
- H1 remains the separate human-reviewed Steam-backed Fail; no H1 or Safe beta
  inference is made.

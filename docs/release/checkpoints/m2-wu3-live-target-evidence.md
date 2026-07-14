<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# M2-WU3 Live Target Evidence Packet

Status: accepted `dev` integration proof; human verdict pending.

This checkpoint records the product-neutral evidence packet and capture
boundary. It does not record a live-target acceptance run, a human `Pass`, a
real Factorio archive acceptance, ordinary managed-portable authority, or
product execution authority.

## Bound identities

| Repository/evidence | Identity |
| --- | --- |
| Universal Setup WU3 task head | `42ff66f8502bf6fea2996c96a56b9762fa6a7e9a` |
| Universal Setup canonical `main` | `fbbeb762f25921ae05945206fd0c004a52239c13` |
| Universal Setup exact-main CI | `29329946351` |
| Universal Launcher retained provider | `6d41e07b76cd19b2a7630835e05ac3aa125d57b8` |
| FacMan provider-pin commit | `2e6012e0b14c738ce83753e9fc9e70c62622d269` |
| FacMan validation/package revision | `ecec3a46e78af54f386d08d9a4a24055f1210bdd` |
| FacMan reviewed PR | `#16` |
| FacMan reviewed task head | `5f93f42f97089ae367e718d3466f4421abf43625` |
| FacMan preserved `dev` merge | `a8b298a35cd1587cea566886b5a3891153a2b7f2` |
| shared task/merge tree | `b634c5b35080ae48d6b19acbc5b3ddbc1564ca9a` |
| exact-`dev` CI | `29332570822` |
| exact-`dev` CodeQL | `29332570777` |
| exact-`dev` security policy | `29332570776` |

## Evidence law

`live_evidence.capture` accepts a strict capture request, then re-reads and
validates setup-owned installed state, ownership, audit chain, and the exact
transaction journal before writing a no-clobber packet. The packet binds exact
Git revisions, setup ABI and contract versions, archive and recipe identity,
target/filesystem classification, reviewed plan identity and totals, actual
closure, state/ownership/audit/journal identities, pre/post snapshots, recovery
state, and bounded automated findings.

Plans expose bounded pre-operation target snapshot digests. Capture independently
recomputes the post-operation target snapshot and refuses stale or substituted
observations. Stored packets use deterministic canonical JSON, stable reads,
digest validation, and immutable filenames.

Runtime capture can emit only a pending verdict. The separate
`live_evidence.verdict.record` command requires explicit `RECORD VERDICT`
confirmation and creates a successor packet for a human `Pass`, `Fail`, or
`Inconclusive`; it cannot rewrite the pending packet.

## Proof result

- Universal Setup exact-main CI passed tests, sanitizer, and bounded fuzzing;
- Universal Setup Release passed 14/14 native tests and 21/21 Python cases;
- FacMan passed 39/39 native tests and 339 Python cases with one opt-in skip;
- required Windows package proof passed 14/14 with zero skips;
- clean three-repository reconstruction passed all builds, CTest, strict,
  AIDE, installed-consumer, and Python gates;
- selected Windows package reproducibility passed over a 386-file tree.
- PR #16 preserved the complete commit series in `dev`; the task head and merge
  have identical Git tree identities;
- exact-`dev` CI, CodeQL, and security policy completed successfully at the
  preserved merge commit.

| Reproducible evidence | SHA-256 |
| --- | --- |
| archive | `9e340185a15d5538e57fa57794438b7040724e9160750a2667fb6fa70bfef462` |
| package tree | `62c98bca2a539ea1145f3a713758bfd2a2ab95d775cac366cea02069e061e4ee` |
| SBOM | `4bc56dff899460a4821b41141f1a3a8c8237e63ce14bf4b3dd55e8e378970004` |
| provenance | `ba069f26869112f3a67ede0a1e4caf68e832246a15c45d5bf91031fb4928692b` |

The artifacts remain unsigned and unpublished; publisher authenticity is not
proven.

## Authority retained

- No mutation occurred under `D:\FacMan-Live-Acceptance\M2` in WU3.
- The human M2 verdict remains `pending`; automation did not create it.
- Ordinary live-target apply remains unavailable pending operator acceptance.
- `recovery.apply` remains unavailable pending WU5.
- Existing Factorio and Steam installations were not touched.
- Network, credentials, registry, shortcuts, elevation, installer execution,
  product execution, signing, publication, H1 promotion, and Safe beta remain
  unavailable.

# FacMan ULK session pin adoption 01

Date: 14 August 2026

State: `implementation_complete_pending_exact_head_hosted_requalification`

## Exact identities

```text
canonical FacMan dev base  51a65689ae12d0d15a48c8faee6494ac83def677
canary history             0e5ce2a018a3ff80a2b93ed6f1554c3350cd7cf3
history-preserving merge   8c409ac7c1201cfcb8730c233bd09749bfa52712
hosted qualification head 6fdad7250717cb8e144d297d5fcb60fe7d848740
atomic implementation      48a455456d3aba1264dc682e0eb04c155ffc9edb
implementation tree        daac1cc2c0e6c2d6c5e603404e0e1ba4a4c5cb7e
ULK main                   09f0639ab6529fba2f2aa22e9bf68e5eebed0553
ULK tree                   d877bfa3a86158f65705facf757e8700a067d077
ULK SDK identity / CMake / ABI  1.8.0 / 1.9.0 / 1.9
ULK synchronized dev       2e77e15c8bcdeb833a0a45aab3421886b72cc70c
prior FacMan ULK pin       1cafe4054297cc11e02458b83d230db0cd064471
USK main                   32488fc13bd2439f9f6e52e83a97f6da345a7650
USK tree                   12fe757b1fc2ae78768a8cf912d03835f46ca65b
```

The canary head is preserved in the adoption branch's ancestry rather than
merged as a separate product state. Pull request #143 is therefore evidence
and reusable history for the atomic adoption, not an independently mergeable
provider configuration.

## Accepted three-platform qualification

Hosted provider SDK run
[`31721583745`](https://github.com/Julesc013/factorio-launcher/actions/runs/31721583745)
completed successfully on Windows 2022 x64, Ubuntu 24.04 x64, and macOS 15
Intel. Every observation records `exact_consumer_canary_pass`, leaves the
tracked lock byte-unchanged, is release-ineligible, and has all ten authority
fields false.

| System | Observation SHA-256 |
| --- | --- |
| Linux x64 | `c31a94fd969859af9d96df8055e194efa5b60e7502a9d4c26ecd65f20bfafbdc` |
| macOS x64 | `59b86352dc38777978acb9e43325514bd12eac5b0990a690a3eed68b5cbcbd4b` |
| Windows x64 | `b4a3c3a1cb2875bc6461e2fecf2ceb6fa052a267985972e2ef64ed27a1d8f1f6` |

The evidence-authored two-provider, three-system, two-linkage package matrix
has canonical digest
`5bf352e944b1df906df9139cf4ef79a3669082ce054ec141167ab80668bab6cd`.
It binds the promoted ULK ABI manifest
`ce17990b20ee3730cb73a709d8a649fdc5234df8b8e9735bf9a6ea0ea992210e`
and contract digest
`b9e39e83dc1ae85755dce4f5f61d23bc438a0e81882313c04ca00f5eff661e4e`.

## Atomic authority cutover

The implementation:

- consumes exact canonical ULK `main@09f0639...` in source, installed-static,
  installed-shared, relocated, package, ABI, SBOM, and dependency truth;
- makes `ulk.session.journal.v1.authoritative` the normal backend Last Run
  provider through the public experimental ABI 1.9 session contract;
- preserves bounded reads, immutable terminal outcomes, interruption recovery,
  restart persistence, `outcome_unknown`, and `recovery_required`;
- removes WinForms, AppKit, and GTK frontend-cache reads as authority inputs;
- makes WinForms read the backend presentation projection, while AppKit and GTK
  expose an explicit unavailable compatibility state until their later cuts;
- retires the default-off consumer-canary build mode and its one-off harness;
- invalidates the old provider-bound successor Play route without altering its
  immutable historical bytes; and
- advances the dependency-ordered plan to
  `FACMAN-SAME-BINARY-TUI-PARITY-CLOSEOUT-01`.

No frontend manufactures a terminal outcome, and no local cache is a fallback
authority.

## Local validation

- provider reconciliation: pass, digest
  `45603ad8ea54cd11ec0f890bf65ecbb576a22e840dcbe7df17bb82a07ae7e729`;
- focused provider and lock tests: 59 pass, one expected local symlink-privilege
  skip;
- fresh tracked-lock native presentation, ULK Last Run, and TUI projection
  smokes: 3/3 pass;
- FLB ABI symbol and relocated current/legacy consumer checks: pass with ULK
  package `1.8.0` and required ABI `1.9` represented independently;
- WinForms x64 Debug build: pass with zero warnings and zero errors;
- strict policy suite: pass;
- AIDE Lite portable suite: pass;
- generated command/version metadata and plan/state projections: current;
- portable discovery: 1,000 tests exercised; after repairing the surfaced
  route-invalidation and truth expectations, the remaining local-only gap is
  the required Windows package fixture under `build/native-smoke`, which is
produced and enforced by hosted CI.

The first atomic exact head, `254cbaa1f8aca4d0635b7386cb2135b7368282b0`,
correctly failed hosted qualification because it had conflated the unchanged
ULK SDK package version `1.8.0` with the promoted ABI version `1.9`, retained
two FLB ABI `1.8` consumer assertions, and omitted the WinForms `System.IO`
import required by `InvalidDataException`. The corrective change updates the
smallest owning contract layers. It does not change the adopted ULK source
revision, ABI, package bytes, provider authority, or product scope.

The next exact-head run exposed a second, narrower version-axis overload in
installed mode. ULK's immutable SDK sidecar and WorkUnit package identity are
`1.8.0`, while the promoted source's CMake project and generated
`UniversalLauncherConfigVersion.cmake` are `1.9.0`; its public C ABI is `1.9`.
FacMan now validates those three values independently. The exact SDK sidecar
and release lock remain `1.8.0`, `find_package` requires the exact CMake
package `1.9.0`, and ABI validation requires `1.9`. Focused contract tests pass;
the exact local harness passed source, installed-static, and relocated-static
configure/build/test/probe paths and configured installed-shared before its
15-minute wrapper expired during compilation. Hosted artifact custody now also
retains nested Phase-A command logs when an SDK-consumption run stops early.

The same exact-head run then exposed one stale presentation test expectation:
an available authoritative ULK journal with no terminal record correctly
projects `no_record`, not `provider_unavailable`. The transport-equivalence
test now asserts both `no_record` and the authoritative ULK provider identity;
the production behavior and schemas were already correct.

The final pull-request head must still complete the full exact-head hosted
matrix. This checkpoint must not be read as merge qualification until those
checks are green.

## Authority ceiling

```text
Factorio execution  false
Setup mutation      false
route promotion     false
permit issuance     false
observer capture    false
signing             false
publication         false
release             false
stable provider SPI false
```

The adoption supplies canonical product infrastructure only. It does not run
Factorio, activate a route, add a daemon, change USK, sign, publish, release,
or claim stable public-provider status.

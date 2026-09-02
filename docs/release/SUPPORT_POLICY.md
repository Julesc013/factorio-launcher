# Support policy

FacMan has no published supported release today. Support is explicit in an
immutable release-ledger entry and is bounded by exact source, package, target,
capability, frontend, and qualification identities. Compilation, a green CI
job, a route definition, or an unsigned archive does not create support.

## Release-class support

| Class | Current support meaning |
| --- | --- |
| Untagged snapshot | unsupported disposable development evidence |
| `0.1.0-alpha.N` | unsupported prerelease; security reports and exact-build defects may be triaged |
| `0.1.0-beta.N` | human-tested prerelease; support only for the ledger's admitted Windows matrix |
| `0.1.0-rc.N` | frozen candidate; release-blocking regressions and security defects |
| Stable `0.x` | public-beta support class and maintenance window stated by its ledger entry |
| Stable `1.x+` | full support class and maintenance window stated by its ledger entry |
| Historical checkpoints | immutable audit/reconstruction evidence, not supported binaries |

No backport window is promised until a stable ledger entry defines one. A
withdrawn or revoked build retains its immutable identity and follows
the withdrawal law in `release/index/version_train.v1.toml` and its exact
append-only ledger record.

## Current supported-version status

- **Current default branch:** receives security triage and reproducible defect
  analysis, but source or CI status does not create a supported release.
- **Historical R2/R3 checkpoints:** remain reconstruction and audit evidence,
  not supported binaries.
- There is **no stable supported release** until an immutable stable ledger
  entry and its separately authorized publication exist.

## Current platform proof

- The current product identity is `facman-0.1.0-alpha.5`. Exact candidate run
  `33576140943`, attempt 1 passed from revision
  `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` and tree
  `1ebcd2b230ed188e021880ffa4c438de2ede655b`, but remains unsupported,
  unsigned, unpublished, and non-authorizing. Alpha.4 is the integrated
  foundation baseline; tagged
  private-draft alpha.3 remains immutable historical evidence.
- Windows CLI, same-binary TUI, and WinForms .NET Framework 4.8 are
  exact-candidate machine-qualified on the Windows 10/11 x64 reference lane.
  Human install, accessibility, packaged performance, real Play, and support
  receipts remain pending.
- Exact local read-only version/help qualification covers Factorio F100
  (`1.0.0`), F110 (`1.1.110`), F200 (`2.0.77`), and F210 (`2.1.14`) without
  launching gameplay or changing the installation trees. This is a bounded
  compatibility observation, not a support promise.
- Ubuntu 24.04 x64/glibc 2.39 GTK3/X11 and macOS 13+ Intel AppKit products are
  exact-candidate machine-qualified semantic previews. Their semantic parity,
  human install/accessibility/performance, and support receipts remain open.
- Qt6 is a scaffold only. Qt6, WinUI, and SwiftUI are post-beta admission lanes,
  not current release or support claims.

The `0.1.0-alpha.5` beta-readiness scope and exact source/provider locks define
the current alpha candidate. The binding receipt is
`release/index/alpha5_promotion_candidate_closeout.v1.toml`; the archived
foundation checkpoint is
`.aide/history/facman-0-1-alpha5-foundation-closed-2026-09-02/index.json`.
The receipt qualifies only `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` /
`1ebcd2b230ed188e021880ffa4c438de2ede655b`; closeout and future
revisions need a fresh candidate run. Earlier candidates are historical
evidence only and their package hashes cannot be reused.

The workflow's 14-file internal bundle is evidence transport, not the final
public artifact matrix. Public release truth remains eight assets: six product
packages, one versioned checksum list, and one consolidated evidence archive.
AppKit and GTK remain preview lanes; supported-release promises and every
deferred capability remain outside the current claim unless their own evidence
and authority records say otherwise.

Compatibility floors are target-profile claims. They may use different
binaries, toolchains, runtimes, frontends, and ULU/USU host providers while
preserving common semantics. A build on a modern runner does not prove Windows
XP, macOS 10.6, or glibc 2.11.1 support.

Exact current floors and evidence live in the release indexes and milestone
matrix. Signing, notarization, human setup-install/lifecycle acceptance,
package-manager publication, self-update, live managed Factorio-install
mutation, and real Factorio execution remain separate claims and authorities.

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
| Stable `1.x` | full support class and maintenance window stated by its ledger entry |
| Historical checkpoints | immutable audit/reconstruction evidence, not supported binaries |

No backport window is promised until a stable ledger entry defines one. A
withdrawn or revoked build retains its immutable identity and follows
`release/index/withdrawal_policy.v1.toml`.

## Current supported-version status

- **Current default branch:** receives security triage and reproducible defect
  analysis, but source or CI status does not create a supported release.
- **Historical R2/R3 checkpoints:** remain reconstruction and audit evidence,
  not supported binaries.
- There is **no stable supported release** until an immutable stable ledger
  entry and its separately authorized publication exist.

## Current platform proof

- Windows CLI has unsigned CI/package evidence on a Windows 10/11 x64 lane.
- Linux CLI has unsigned hosted proof on the recorded runner/glibc profile.
- macOS CLI has unsigned hosted proof on the recorded Intel/deployment profile.
- WinForms, AppKit, GTK, and TUI surfaces currently have differing fixture,
  compile, package, and runtime evidence; none is a published support claim.
- Qt is a planned product lane and is not current implementation evidence.

The intended `0.1.0` public beta admits Windows 10/11 x64 CLI, TUI, and
WinForms only. Every admitted semantic capability must pass the matrix's
positive, refusal, fault, recovery, package, accessibility, documentation, and
support gates. AppKit, GTK, and Qt mature on later 0.x trains and all six
frontends are required for the measurable `1.0.0` contract.

Compatibility floors are target-profile claims. They may use different
binaries, toolchains, runtimes, frontends, and ULU/USU host providers while
preserving common semantics. A build on a modern runner does not prove Windows
XP, macOS 10.6, or glibc 2.11.1 support.

Exact current floors and evidence live in the release indexes and milestone
matrix. Signing, notarization, setup installers, package-manager publication,
self-update, Setup mutation, and real Factorio execution remain separate
claims and authorities.

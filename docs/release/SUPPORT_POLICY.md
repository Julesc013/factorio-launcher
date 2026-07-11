# Support policy

FacMan is pre-1.0 and has no stable supported release. Support is explicit by
source revision, release profile, and proof lane; repository contracts alone do
not create a support promise.

## Version support

| Version or ref | Status | Scope |
| --- | --- | --- |
| Current default branch | development support | issue triage and current CI |
| Named `0.1.0-dev` package preview | preview only | exact artifact/profile proof |
| Historical R2/R3 checkpoints | unsupported evidence | reproducibility and audit only |
| Unnamed local builds | unsupported | developer responsibility |

Only the current default branch and an explicitly named preview candidate
receive security triage. No backport window is promised before a stable release
policy is approved.

## Platform proof scope

- Windows CLI: Windows 10 22H2 x64 baseline, unsigned local/CI package proof.
- Linux CLI: Ubuntu 24.04 x64 runner and glibc 2.39 baseline, unsigned target-CI proof.
- macOS CLI: Intel x64 with deployment target 13.0, unsigned target-CI proof.
- WinForms and AppKit are legacy/compile or command-client evidence only.
- TUI, daemon, WinUI, SwiftUI, GTK, and Qt are not published supported products.

Exact floors live in `release/index/support_matrix.v1.toml` and must be verified
for every candidate. Signing, notarization, installers, package-manager
publication, self-update, setup mutation, and real Factorio execution are not
support claims.

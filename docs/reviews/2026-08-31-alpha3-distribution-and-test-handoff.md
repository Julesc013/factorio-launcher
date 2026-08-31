# Alpha.3 distribution and manual-test handoff

Date: 31 August 2026

WorkUnit: `FACMAN-ALPHA3-DISTRIBUTION-CONVERGENCE-01`

Candidate: `0.1.0-alpha.3`

## Decision

Alpha.2 remains immutable engineering evidence but is superseded for
user-facing distribution. Alpha.3 is the first candidate whose primary
downloads consistently present FacMan as one cross-platform product:

```text
FacMan   GUI
facman   JSON CLI, human CLI, and same-binary TUI
```

The release remains a GitHub draft prerelease. Publishing, signing, support
promotion, and real-Factorio execution authority remain absent.

## Exact acceptance inventory

The candidate is valid only if the draft has exactly the six platform product
packages, checksum text, and consolidated evidence ZIP listed in
`release/index/alpha3_release_source.v1.toml`. Any extra standalone JSON,
SBOM, provenance, licence, CLI, TUI, or toolkit-branded asset is a release
assembly failure.

## Manual observation record

Create one record per package and machine:

```text
Package:
SHA-256:
Machine:
OS/version:
Architecture:
Portable or setup:
GUI start/result:
facman --help result:
JSON command/result:
facman tui result:
verify/repair/uninstall result:
Workspace preservation:
Unexpected files/effects:
Defects:
Verdict: pass | fail | inconclusive
```

Keep portable extractions separate from installed tests. Use a fresh empty
directory for every portable retest. Do not run the separately controlled real
Factorio route during ordinary exploratory testing.

## Beta decision

After observations return:

1. classify defects by package hash and platform;
2. repair product or distribution defects forward-only;
3. require a new prerelease version for any byte change;
4. allocate beta.1 only when the user says the combined package behavior is
   ready for beta;
5. repeat the exact build, qualification, draft-release, download-back, and
   manual-verdict cycle until the user declares 0.1.0 stable.

## Beyond 0.1.0

Post-0.1 work may address signing/notarization, Apple Silicon/universal2,
additional Linux/Wayland profiles, optional consented PATH integration,
automatic update design, richer native maintenance UI, and public support.
None is silently included in the alpha.3 claim.

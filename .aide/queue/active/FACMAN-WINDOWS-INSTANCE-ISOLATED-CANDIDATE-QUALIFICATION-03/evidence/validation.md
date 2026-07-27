# Validation

## Stable-I/O interoperability repair

The native-result digest repair passed the complete local promotion matrix,
the full hosted matrix at exact PR #90 head
`051378d5f8edead4be8dcd04657ca01280e6e1cc`, and merged to `origin/dev` as
`04c7fb0d54ef8f41948cb301d739bda4e980d1b3`.

## Superseded remote-only source closure

A second qualification attempt reconstructed and validated three new empty
no-local HTTPS clones at:

- FacMan: `04c7fb0d54ef8f41948cb301d739bda4e980d1b3`
- Universal Launcher: `7fc25340623131ba86c08dca4fb8a43b18a4520d`
- Universal Setup: `3f8489275077347c2918f3bb03614ec6431362ff`
- source-closure report SHA-256:
  `a036b788e853cd7a1f7adabaef68ea4074013096ec9c596bd94b52d9d2523df5`
- FacMan native tests: `58`
- FacMan Python tests: `553`
- Universal Launcher native tests: `5`
- Universal Setup native tests: `16`
- required Windows package tests: `14`
- package SHA-256:
  `6c628adf6d3d979fa3aa4f70977fab3ad24f0b5a0be3e3c6488cbacd4354dd0c`
- provenance SHA-256:
  `f231d2036d2007c5d2cb18a87e632a09b41c91ba5722f90b097fe612d8d9e8f8`
- source worktrees clean after validation: `true`

The qualification producer advanced through native-result digest validation
and stopped fail closed before producing a binding:

```text
Universal Setup refused bounded archive inspection:
source is not a bounded classic ZIP archive
```

The authenticated owned source archive is a valid 4,361,315,497-byte
single-disk ZIP64 archive. Its 19,737 entries include 2,452 central-directory
records whose local-header offsets require ZIP64 metadata. Therefore this
closure is diagnostic only and is superseded by the provider repair.

## Universal Setup ZIP64 provider repair

Universal Setup PR #18 added strict bounded single-disk ZIP64 inspection while
retaining stable no-follow reads, exact local/central agreement, path and type
refusals, count/size/ratio limits, and fail-closed elapsed budgets.

- repair head:
  `c8501e9281ae63bf4e3c892a5d2faec0a5790e1d`
- canonical `main` merge:
  `3048128963dc718a7c38c1cfcdda9e813a23b0db`
- local native tests: `16/16`
- local Python contract tests: `21/21`
- local strict validation: `pass`
- hosted Windows, Linux, macOS, sanitizer, and fuzz-smoke jobs: `pass`
- hosted workflow run: `30291731746`

The patched provider then passed a real non-executing FacMan integration check:

- source archive SHA-256:
  `ad36e059...` (full value remains in the private owned-source evidence)
- exact member:
  `Factorio_2.0.77/bin/x64/factorio.exe`
- materialized size: `43,530,192`
- materialized SHA-256:
  `d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b`
- Factorio execution: `false`

## FacMan provider synchronization

FacMan now consumes Universal Setup
`3048128963dc718a7c38c1cfcdda9e813a23b0db` from a fresh HTTPS clone.

- local exact-pin workspace doctor: `pass`
- explicit remote reachability verification: `pass`
- native build and CTest: `57/57 pass`
- Python promotion obligations: `551 pass`, `9 skipped`
- required blocked skips: `0`
- unknown skips: `0`
- optional skips: `7`
- unsupported skips: `2`
- strict validation: `pass`
- project-state validation: `pass`
- AIDE Lite validation: `pass`
- `git diff --check`: `pass`

## Authority exclusions

No Factorio process, observer, baseline, permit, human verdict, route
promotion, policy change, Setup mutation, signing, or publication operation
was performed.

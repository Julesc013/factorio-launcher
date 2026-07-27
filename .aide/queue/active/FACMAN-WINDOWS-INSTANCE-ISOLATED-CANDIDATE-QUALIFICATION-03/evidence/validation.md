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

## Hosted provider synchronization

FacMan PR #91 passed the exact-head hosted `security-policy`,
`code-security`, and complete six-job cross-platform `ci` matrix at
`593af834aa4586a1e595c3c6474880fd8d8f2d71`. It merged to `origin/dev` as
`3d18be3ad1c2d874e7d3ce27fc99f7590d41962e`.

## Third remote-only source closure

Three new empty no-local HTTPS clones reconstructed:

- FacMan: `3d18be3ad1c2d874e7d3ce27fc99f7590d41962e`;
- Universal Launcher: `7fc25340623131ba86c08dca4fb8a43b18a4520d`;
- Universal Setup: `3048128963dc718a7c38c1cfcdda9e813a23b0db`.

The closure passed:

- report SHA-256:
  `bc5c38208791596e583acc8db6c327f872944bb18db1d378a68a4e8581afd793`;
- FacMan native tests: `58`;
- FacMan Python tests: `553`;
- Universal Launcher native tests: `5`;
- Universal Setup native tests: `16`;
- required Windows package tests: `14/14`;
- package SHA-256:
  `80a3460ccb4b7506c40bef2113ff5132120f3fb7df674c32b427c173a3d4acc8`;
- provenance SHA-256:
  `735c884f406de6be5ba07af056504fecbc28b7ee4fcdb6f8210420dccd9ff569`;
- source worktrees clean after validation: `true`.

## Superseded qualification binding

The fresh producer passed and emitted:

- qualification digest:
  `8ebad51283d0440ca6edd07551dc400162c73de2c76b1eef4ee8e10c835db113`;
- binding SHA-256:
  `55c26160bcb05f0ebb3395f1b46b7cc6dda22c294eb6efde15bb1e50ecbae2a1`;
- report SHA-256:
  `e91ffb4c52eda2ba69c35108bb57908cd4939b1dd51b5aacd44cec96ecb90294`;
- exact Factorio executable SHA-256:
  `d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b`;
- authenticated source archive SHA-256:
  `ad36e0591e336400e731d5b400038e37c8361fdc71c76c0f6db96ee31741b4c2`.

The qualification is valid for its exact source, but is superseded as final
qualification-03 evidence because staging exposed a source-changing handoff
repair.

## Fail-closed stage handoff finding

Coordinator `stage` rebuilt the disposable revalidation workspace and then
refused before config or artifact-binding creation:

```text
prequalified candidate state differs from its immutable binding
```

Read-only projections proved the exact cause:

- `InstanceSpec` digest remained
  `4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79`;
- qualification-workspace `InstanceBinding` and readiness digests were
  `f95bc3d17254fc0f73831638e82d121d43624ce7fa54cb9c1371b68edc587623`
  and
  `f0ab71b396fe39050953063c4c36f3badabd14a05e94dc97ab2f45647fa64677`;
- revalidation-workspace `InstanceBinding` and readiness digests were
  `16eabc593163a21c8d2df76d283ad5816d7aaa90ef1240e2d7eb7466f04d325b`
  and
  `39111e536439e5b572b1dbc613f33ebf5e8948493fa6b0bdda4b9e3bddcb78e0`.

The difference is required because the latter two identities bind exact
absolute config and mod paths. Equating values from two different WorkUnit
roots is impossible and would make every correct stage fail.

## Staged-candidate handoff repair

The bounded repair:

- preserves the immutable qualification and root-independent `InstanceSpec`;
- performs fresh non-executing projections in the final workspace;
- seals the exact final `InstanceBinding`, readiness, and full projection
  digests in a closed staged-candidate record;
- binds that record to the qualification digest and exact workspace;
- requires later preflight to reproduce the staged record;
- validates operation IDs before expensive staging;
- rejects binding, workspace, projection, digest, and authority substitution.

Focused coordinator, preflight, and qualification tests pass: `38`, with two
explicit unsupported symlink cases skipped. No Factorio process, observer,
baseline, permit, human evidence, verdict, route promotion, policy change,
Setup mutation, signing, or publication operation was performed.

The complete promotion profile also passes:

- tests: `553`;
- required-blocked skips: `0`;
- unknown skips: `0`;
- optional skips: `7`;
- unsupported skips: `2`;
- failures/errors/unexpected successes: `0/0/0`;
- gate passed: `true`;
- strict validation with exact provider worktrees: `pass`;
- project-state validation: `pass`;
- AIDE Lite validation: `pass`;
- `git diff --check`: `pass`.

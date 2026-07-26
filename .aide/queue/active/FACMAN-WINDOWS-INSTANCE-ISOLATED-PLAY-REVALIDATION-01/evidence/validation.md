# Validation

Status: BLOCKED AFTER PRELIMINARY QUALIFICATION.

This WorkUnit is active and prepared, but no candidate qualification, observer
session, permit issuance, WPR capture, Factorio launch, human journey, or
operator verdict has occurred.

The prerequisite runtime/evidence separation is accepted at merged `dev`
revision `d03b42e8d6b22459fd9a9b8feff05523f942577a`, with exact merged runs:

- CI `30212150312`: PASS;
- code security `30212150359`: PASS;
- security policy `30212150353`: PASS.

Any eventual result must be exactly `Pass`, `Fail`, or `Inconclusive` and must
bind a newly built exact candidate plus entirely fresh evidence.

On 2026-07-26 a preliminary clean-worktree build at merged `dev`
`b874a40ccba747565c34b726bd6c0d94c9dc1be0` proved that the separated
candidate still compiles and passes its focused synthetic checks against ULK
`7fc25340623131ba86c08dca4fb8a43b18a4520d` and USK
`3f8489275077347c2918f3bb03614ec6431362ff`:

- six focused native candidate, permit, packet and privilege checks: PASS;
- 92 focused Python tests: PASS, with two sandbox-symlink skips;
- strict validation: PASS, 298 schemas;
- project-state validation: PASS;
- portable AIDE validation: PASS;
- exact merged-dev CI `30213373783`: PASS;
- exact merged-dev code security `30213373796`: PASS;
- exact merged-dev policy `30213373804`: PASS.

This is not the required candidate-qualification proof because the build used
clean pinned worktrees rather than three fresh remote clones. It issued no
permit and produced no observer, baseline, packet, WPR, Factorio or human
evidence.

Inspection also proved that the existing real-Play coordinator and native
harness are still hard-bound to the historical hermetic policy and
`isolation_mode = hermetic`. They cannot lawfully produce an
`instance_isolated` verdict. Revalidation is therefore blocked until the
separate qualification and operator-harness prerequisite is accepted.

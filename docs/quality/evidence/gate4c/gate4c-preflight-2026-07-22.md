# Gate 4C preflight checkpoint

Date: 2026-07-22

WorkUnit: `FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01`

Disposition: `blocked_before_baseline_or_permit`

## Authority result

No permit was issued, no process was started, no Factorio run occurred, and no
human verdict was recorded. The product Play route remains unavailable.

The evidence-only preflight record was written outside the repositories to the
task-owned Gate 4C root. Its identities are:

```text
preflight digest  12d16c64796af2ff2b7ccd122ea0fd39aca0fc2a3d9065f7278c13e9dc468689
packet SHA-256    47a86630526af06922446c582862dc2341b242249dfb0d362ca611f3fe4819df
artifact manifest ad82e7cf2a7df4d81408218a36deae4188dca2960e872bbbd9489f463cb922d0
ownership record  caa2814083951e02062dc67b5b49c86ce1c8e604a1e1ce6cc8be90d9ce0abae7
```

## Satisfied bindings

The preflight verified:

- frozen policy digest
  `6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2`;
- reviewed candidate ancestry through final evidence `dev`
  `6f883cd00e7a06b1b804cb7d868d212b83c10952`;
- exact Universal Launcher and Universal Setup revisions;
- the copied reviewed Gate 4B artifact manifest and FacMan executable SHA-256
  `47ccf1f151eb65daea1ae4d8ff782f48df08bbedd92d9434e5ca6fd86536270a`;
- Wube-signed Factorio 2.0.77 executable SHA-256
  `d3bcfca4dbee407d472013b745ce2445d34af6f021aacc5753ee0dac54b56b0b`;
- the dedicated disposable instance, explicit empty mod lock, current spec,
  binding, and readiness digests;
- the exact four-argument menu launch shape using only `--config` and
  `--mod-directory`;
- no product permit or execution authority in the read-only instance state;
- WPR, XPerf, and WPAExporter are installed and WPR has no active recording.

## Closed blockers

The run is prohibited until all five blockers are resolved and a new preflight
record is produced:

1. `authenticated_source_evidence_missing`: the original installer/source
   artifact is unavailable. The installed signed executable is not substituted
   for the frozen policy's source-artifact evidence.
2. `host_not_quiet`: Steam and Steam Web Helper processes are active.
3. `observer_elevation_required`: the current medium-integrity session cannot
   enable the FileIO/Registry WPR profiles; the attempted self-test returned
   `0xc5585011` and WPR confirmed that no recording remained active.
4. `observer_self_test_missing`: no complete, zero-loss, attribution-complete
   observer self-test artifact exists yet.
5. `quiet_host_attestation_missing`: the operator has not yet attested that
   pending restart, competing FacMan/Factorio processes, unrelated install or
   synchronization activity, and sleep/restart risk are controlled for the
   run interval.

These are preflight blockers, not a `Fail` or `Inconclusive` human verdict,
because the frozen operation has not begun.

## Scratch cleanup

The exact Gate 4B scratch root was verified as task-owned, directly beneath the
approved temporary parent, non-reparse, and unused by a process. Required
reviewed artifacts were copied and hash-verified into the Gate 4C root. The
only old-path occurrences are embedded debug/build strings in those copied
binaries and are not live dependencies.

The approved exact-root recursive deletion was attempted once. The command
guard rejected it before deletion, so the 15.62 GiB root remains intact. No
bypass, wildcard deletion, ancestor deletion, or unrelated cleanup was
attempted.

## Tooling

`tools/gate4c_verdict_preflight.py` implements the closed, non-executing
preflight packet. `tools/gate4c_observer_self_test.py` implements the elevated
observer probe and refuses to run without elevation. Neither tool can issue a
permit, start Factorio, modify runtime code, change the policy, or record the
human verdict.

The quiet-host attestation is a strict JSON object with schema
`factorio.gate4c_quiet_host_attestation.v1`, an `attested_at` value, a
provider-scoped `reviewer_id`, and exactly these true booleans:

```text
pending_restart_cleared
steam_closed
unrelated_factorio_facman_closed
install_backup_sync_activity_paused
sleep_and_restart_prevented_for_run
```

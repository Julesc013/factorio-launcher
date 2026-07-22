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
4. `observer_self_test_missing_or_stale`: no complete, fresh, exact-machine,
   exact-tooling, zero-loss, per-domain attribution-complete observer self-test
   artifact exists yet.
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

The hardened quiet-host attestation is a strict JSON object with schema
`factorio.gate4c_quiet_host_attestation.v2`. It binds a UTC `attested_at`, a
provider-scoped `reviewer_id`, the current opaque machine and boot identities,
the exact observer self-test digest, the current host-state digest, and exactly
these true booleans:

```text
pending_restart_cleared
steam_closed
unrelated_factorio_facman_closed
install_backup_sync_activity_paused
sleep_and_restart_prevented_for_run
```

The timestamp may be at most 30 seconds in the future and the attestation
expires after 600 seconds. A ready preflight records the same deadline as
`baseline_must_begin_before`; the complete preflight must be rerun immediately
before baseline capture. The attestation must be newer than the bound observer
self-test, and the baseline deadline is the earlier of the observer and
attestation expiries. A restart, observer replacement/failure, competing
Steam/Factorio/FacMan process-state change, sleep, installation activity, or
other materially changed host state requires a new attestation.

## Pre-execution evidence hardening

The PR #55 review hardened four prerequisites before any baseline, permit, or
Factorio process is allowed:

1. Source evidence is now an operator-supplied, recognized Wube Windows
   installer. Its PE product, description, original filename, Wube signer and
   timestamp signer are recorded; its product version is exactly `2.0.77`; and
   both its stable file identity and SHA-256 must differ from the installed
   `factorio.exe`. Installed executables, unrelated Wube-signed executables,
   wrong-version installers, unsigned renamed files, and reparse paths are
   refused.
2. Attestation timestamps are parsed as UTC and bounded by the 600-second
   lease. Provider-less reviewer strings, stale or future timestamps, and any
   machine/boot/observer/host-state mismatch are refused.
3. `factorio.gate4c_observer_self_test.v2` binds the WorkUnit, candidate
   revision, provider ID/revision, clean FacMan tool commit, both evidence-tool
   script hashes, opaque machine and current boot, elevation, generation time,
   WPR/XPerf/WPAExporter identities and versions, trace/dump/stats hashes, and a
   canonical self-test digest. It expires after 900 seconds.
4. ETW attribution is no longer aggregate. FileIO and Registry markers must
   each identify the parent probe PID and correct event class. Process-start
   evidence must identify the parsed child PID and its expected parent PID.
   A wrong PID or event class in any one domain makes
   `attribution_complete = false`.

These changes remain evidence tooling only. They do not alter runtime code, the
frozen policy, the Gate 4B candidate, product authority, or the historic
`blocked_before_baseline_or_permit` result above.

The hardening diff passed 21 focused tests (two host-privilege-dependent
symlink cases skipped, with an unconditional mocked reparse refusal also
passing), `source_format_check.py`, `strict_check.py`, and the portable AIDE
Lite test. A task-owned external Windows Debug build then passed the complete
native CTest and Python matrix: 396 Python tests passed with 30 intentional
target/toolkit skips. The external build lived only under the recorded Gate 4C
temporary root; no source-repository build tree was created. Its exact-root
cleanup command was rejected by the command guard before deletion, so the
owned `pr55-hardening-build` subtree remains retained with its ownership marker
instead of being removed through a bypass.

# Gate 4C preflight

The first exact-candidate preflight completed without issuing a permit or
starting a process. The detailed checkpoint is
`docs/quality/evidence/gate4c/gate4c-preflight-2026-07-22.md`.

Disposition: `blocked_before_baseline_or_permit`.

Open prerequisites:

- provide the exact Wube-authenticated source artifact;
- close Steam and Steam Web Helper for the quiet interval;
- run the ETW observer self-test from an elevated operator prompt;
- bind a complete, zero-loss observer self-test artifact into a fresh
  preflight;
- provide the strict quiet-host operator attestation immediately before
  baseline capture.

The draft tooling checkpoint now fails closed on four reviewed evidence laws:

- the source must be a recognized operator-supplied installer whose stable
  identity and SHA-256 differ from the installed executable;
- the provider-scoped quiet-host attestation is UTC parsed, machine/boot/host
  bound, and expires after 10 minutes;
- the observer self-test is exact-machine, exact-boot, exact-tooling, exact-tool
  and artifact-hash bound, and expires after 15 minutes;
- FileIO, Registry, and process-start probes must each match their own expected
  PID and ETW event class, including the child-to-parent process relationship.

An expired ready record cannot authorize baseline capture. The complete
preflight must be rerun immediately before the baseline, within the attestation
lease. Any restart, Steam/Factorio/FacMan process-state change, observer/tool
change, sleep, or materially changed host state invalidates the evidence.

Pre-commit hardening validation passed the focused evidence-tool tests, strict
repository checks, AIDE Lite, and a complete external Windows native/Python
matrix (396 Python tests passed; 30 intentional skips). The task-owned build
tree was kept outside the repository. Its exact-root cleanup was rejected by
the command guard before mutation, so it remains retained and explicitly owned;
no deletion workaround was attempted.

This is not a human `Pass`, `Fail`, or `Inconclusive` verdict. Gate 4C remains
active and product Play remains unavailable.

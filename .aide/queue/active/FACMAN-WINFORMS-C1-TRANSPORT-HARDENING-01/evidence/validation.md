# Validation evidence

## Pre-implementation

- Exact FacMan base: `bfac7ce41f19856522b5f9603320f444b8f45094`.
- `main...dev`: `0/0` before task-branch creation.
- AIDE `git policy`: pass.
- AIDE `git detect`: trunk with `dev` integration; task branch required.
- AIDE clean `git plan`: `ready_dry_run`.
- AIDE `task inspect`, `task noop-check`, and `task recover`: missing task
  surfaces demonstrated before activation.

## Red characterization

`python tools/winforms_transport_legacy_red_probe.py` compiled the exact
pre-hardening WinForms sources against .NET Framework 4.8 and demonstrated:

- absent result fields synthesized `ok`, `completed`, and fresh identities;
- exit-zero non-JSON output projected as success;
- missing response identities were substituted from request identities;
- malformed post-dispatch JSON became `refused_before_effects`;
- wrong schema, protocol, request, command, operation, and attempt identities
  were accepted;
- invalid UTF-8 replacement-decoded into apparent success; and
- a one-character limit accepted a two-byte UTF-8 value.

Disposition: expected red; the permanent Windows behavior harness replaces
this legacy-only probe after the repair.

## Green validation

Pending implementation and validation.

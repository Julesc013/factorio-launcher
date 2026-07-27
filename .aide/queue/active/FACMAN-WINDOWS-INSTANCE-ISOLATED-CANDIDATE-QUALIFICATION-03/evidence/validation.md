# Validation

## Initial remote-only source closure

The first qualification attempt reconstructed and validated the exact accepted
source set:

- FacMan: `02add47c0fa74f2299bb68f16532254d4d00ab7e`
- Universal Launcher: `7fc25340623131ba86c08dca4fb8a43b18a4520d`
- Universal Setup: `3f8489275077347c2918f3bb03614ec6431362ff`
- source-closure status: `pass`
- FacMan native tests: `58`
- FacMan Python tests: `552`
- Universal Launcher native tests: `5`
- Universal Setup native tests: `16`
- required Windows package tests: `14`
- source worktrees clean after validation: `true`
- Factorio execution: `false`
- permit issuance: `false`
- authority promotion: `false`

This closure is diagnostic input only. It cannot become final qualification-03
evidence because the qualification producer exposed a source-changing
interoperability repair after the closure completed.

## Fail-closed qualification stop

The producer stopped before creating the qualification task root:

```text
instance-isolated-candidate-qualification:
native evidence result digest is invalid
```

The native result digest was:

```text
dbf86f31f5c568d41f5e642f93ce07667f6eac8679382bd33dfaf800a030e194
```

Reproducing both canonical byte forms proved that the native digest exactly
matched the slash-escaped form and did not match Python's unescaped form.

## Repair validation

- focused stable-I/O, candidate-qualification, and coordinator tests:
  `22 passed`
- focused AIDE, stable-I/O, qualification, coordinator, and architecture
  tests: `48 passed`
- real native probe read of the remote-source-closure report: `pass`
- promotion obligations: `551 passed`, `9 skipped`
- required blocked skips: `0`
- unknown skips: `0`
- optional skips: `7`
- unsupported skips: `2`
- project-state generation and validation: `pass`
- strict validation with exact configured Universal worktrees: `pass`
- AIDE Lite validation: `pass`
- `git diff --check`: `pass`

No Factorio process, observer, baseline, permit, human verdict, route
promotion, signing, or publication operation was performed.

# FACMAN-C1-LIVE-SHELL-INTEGRATION-01 checkpoint

- Exact base: `8f99e968e336b10eef3665a01f21f9c94a0a24e6`
- Branch: `task/facman-c1-live-shell-integration-01`
- Product result: all three C1 shells default to backend-derived presentation
  over the existing bounded process RPC.
- Evidence mode: explicit `FACMAN_PRESENTATION_MODE=evidence`; deterministic
  fixtures remain unchanged.
- Play: no current authority. The UI exposes the backend blocker and dispatches
  only exact registered `run.execute` after fresh backend enablement.
- Operation truth: frontend closure cannot publish completion; Last Run caches
  only a backend-completed launch session as an invalidatable view copy.
- Recovery: read from `workspace.recovery.inspect`, applied only after explicit
  user confirmation, and never followed by automatic launch.
- Route, provider, pins, transport, and revalidation procedure: unchanged.
- GTK payload projection: executable Meson/GLib regression proves a completed
  launch payload is not confused with the enclosing transport schema; CI runs it.
- Next executable WorkUnit: `C1-WINDOWS-RELEASE-CANDIDATE-01`.

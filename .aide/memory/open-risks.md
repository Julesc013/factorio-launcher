# FLaunch Open Risks

- Risk: The repo may harden the current directory structure too early.
  - Status: open
  - Mitigation: Keep structure policy explicit but advisory where it affects
    future universal setup/launcher splits. Document improvement options before
    writing substantial native code.

- Risk: Gateway forwarding, provider/model calls, UI, runtime, and autonomous loops remain deferred.
  - Status: accepted limitation
  - Mitigation: AIDE Lite use remains local, deterministic, and report/review
    oriented unless a future reviewed task enables those surfaces.

- Risk: Python prototype behavior may become accidental architecture.
  - Status: open
  - Mitigation: Treat Python as prototype/golden harness only. Native features
    enter through the command graph, schema, handler, audit, and tests.

- Risk: Universal setup or launcher semantics may leak into the Factorio binding.
  - Status: open
  - Mitigation: Track boundary findings and defer universal repo finalization
    until the split design is discussed separately.

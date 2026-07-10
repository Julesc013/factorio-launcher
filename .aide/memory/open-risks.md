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
  - Mitigation: Keep Universal Launcher product-neutral, keep setup mutation in
    Universal Setup, and route Factorio semantics through registered FLB
    handlers into typed application operations.

- Risk: Static command-graph metadata can drift from registered dispatch.
  - Status: mitigated for the current registry descriptor versions
  - Mitigation: Derive introspection from retained runtime descriptors and
    prove graph-to-dispatch parity before adding more authoritative routes.

- Risk: The generated instance configuration may not isolate real Factorio
  writes.
  - Status: open
  - Mitigation: Parse and preflight the same effective configuration passed by
    `--config`, refuse unsafe roots, add an exclusive instance lock, and keep
    `run.execute` unavailable until the operator Factorio smoke passes.

- Risk: A diagnostic bundle could cross a link, exceed resource budgets, or
  expose malformed structured input.
  - Status: foundation proven; general export remains quarantined
  - Mitigation: Use only allowlisted bounded no-follow traversal, emit explicit
    omissions, fail closed on malformed JSON/INI, and require a separate full
    bundle adversarial promotion before enabling export.

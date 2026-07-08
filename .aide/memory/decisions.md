# FLaunch Decisions

- Decision: AIDE Lite is development governance tooling, not runtime.
  - Status: accepted
  - Rationale: FLaunch production packages target native C/C++ kernels and
    platform frontends. AIDE provides repo-local context, validation, review,
    and advisory planning.

- Decision: Keep a single top-level `source/` root unless a later structure
  review proves a better alternative.
  - Status: accepted for current iteration
  - Rationale: Public ABI headers live in `include/`; private implementation,
    app implementation, and prototypes live under `source/`. Nested `src/` and
    nested `source/` folders are forbidden.

- Decision: CLI, TUI, WinForms, AppKit, GTK, and Qt are sibling frontends.
  - Status: accepted
  - Rationale: No frontend should sit on top of another frontend as its real
    foundation. All frontends call the command graph, daemon, or C ABI.

- Decision: Universal Setup and Universal Launcher remain separate ownership
  discussions.
  - Status: accepted
  - Rationale: Setup mutation and launcher orchestration have different domain
    structures. Do not force both repos into the exact Factorio product layout
    before design review.

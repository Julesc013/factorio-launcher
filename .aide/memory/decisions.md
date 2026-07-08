# FLaunch Decisions

- Decision: AIDE Lite is development governance tooling, not runtime.
  - Status: accepted
  - Rationale: FLaunch production packages target native C/C++ kernels and
    platform frontends. AIDE provides repo-local context, validation, review,
    and advisory planning.

- Decision: Retire `source/` and use ownership roots.
  - Status: accepted
  - Rationale: `runtime/`, `apps/`, `content/`, `contracts/`, and `release/`
    describe ownership more clearly than a broad source bucket. `src/`,
    `source/`, `data/`, `schemas/`, and `packaging/` are forbidden retired
    roots.

- Decision: CLI, TUI, WinForms, AppKit, GTK, and Qt are sibling frontends.
  - Status: accepted
  - Rationale: No frontend should sit on top of another frontend as its real
    foundation. All frontends call the command graph, daemon, or C ABI.

- Decision: Universal Setup and Universal Launcher are sibling repos, not
  Factorio subtrees.
  - Status: accepted
  - Rationale: Setup mutation and launcher orchestration have their own public
    ABI, runtime, contract, content, release, docs, tests, and tool surfaces.

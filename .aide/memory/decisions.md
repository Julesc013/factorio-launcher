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

- Decision: Treat the public C ABI as an experimental correctness floor.
  - Status: accepted
  - Rationale: Size checks, ownership rules, ABI queries, and native smoke prove
    a bounded layout discipline; they do not yet prove stable third-party
    compatibility.

- Decision: Windows read-only discovery is implemented and is no longer the
  next product task.
  - Status: accepted
  - Rationale: Provider tests cover registry and Steam roots, bounded VDF
    parsing, standalone roots, de-duplication, malformed metadata, long and
    Unicode paths, read-only behavior, and junction refusal. Registry truth and
    instance isolation are the next gaps.

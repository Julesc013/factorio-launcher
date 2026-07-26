# Changed files

- Generated exact FacMan, Universal Launcher, and Universal Setup build identity
  in CMake and exposed it through the read-only `workspace.status` projection.
- Reworked `tools/dev.py` around configuration-aware CTest inventory, external
  task roots, current reconfiguration, exact CLI/TUI artifact export, and
  persisted promotion evidence.
- Replaced the stale fast-test list with required, optional, and exact target
  mappings derived from the configured test graph.
- Added the test-obligation policy and runner, classified all live skip sites,
  and changed Linux, Windows, and macOS CI lanes to the promotion profile.
- Added compact current-state generation and exact local promotion scorecard
  fields.
- Archived 23 closed or superseded AIDE task records into
  `.aide/history/completion-baseline-2026-07-26/`; its `index.json` digest is
  `4dd321339cc87e9920721b3c6133cdbdad3f24ba1de86872041f1f9b279fa293`.
- Added a traversal-safe active-or-archived task evidence resolver and migrated
  historical validators away from hard-coded active-queue paths.
- Updated contributor, testing, build-root, roadmap, and generated state
  documentation to the current WorkUnit and no-authority boundary.

The workspace lock, frozen Play policies, capability policy, permit authority,
and product execution routes were not changed.

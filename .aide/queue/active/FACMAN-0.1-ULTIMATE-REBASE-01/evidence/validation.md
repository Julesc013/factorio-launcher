# Validation

## Definitive local promotion gate

- The product native configuration built successfully with shared runtime
  libraries; all 40 native tests passed.
- The release native configuration built successfully with static runtime
  libraries and supplies the portable console/TUI stage.
- The WinForms Release build completed with zero C# warnings and zero errors.
- The full Python promotion selection completed 1,367 tests with zero failures
  and zero errors. Nine skips were explicitly classified: two optional, five
  unsupported, and two not applicable. No required or unknown obligation was
  skipped.
- The exhaustive strict validator completed successfully inside the promotion
  run, including schema, generated-index, release, architecture, packaging,
  security, source-closure, and engineering-budget gates.
- The package-contract TCK passed for all three platform product stages.
- Canonical-v2, portable CLI, portable TUI, and Windows shared-runtime package
  smoke tests passed. The optional generic artifact test skipped only where the
  static portable stage intentionally has no `ulk_shared` library.
- AIDE Lite self-validation, generated project-state reconciliation, resource
  pack tests, provider-workspace tests, and checkout hygiene checks pass.

## Reproducibility identities

- Base revision: `1f20f140a4e999dfd84b93e28a88812ab36a01f7`.
- ULK provider revision: `5479939ca5cbc9ee0f901608a92012778b4752ae`.
- USK provider revision: `d2a2aae7e61c47035c92334b0522143b4fea3880`.
- Embedded resource pack: 592 entries and 2,222,288 bytes.
- Resource content digest:
  `3eb3fb62e6a41fc1d1ed0601a04b4112e6eff168cd5cb79341d4d1f9a2ab0fe7`.
- Resource ZIP SHA-256:
  `071436d9a6a9c6752f1657e51c3232467c46104d6a4a743bdbf350471e0394cf`.

The durable machine-readable promotion receipt is held under the marker-owned
external task root as `evidence/python-obligations-promotion.json`. It reports
`gate_passed: true`, `required_blocked: 0`, and `unknown: 0`.

Protected-branch checks, final artifact hashes, and merge revisions are closeout
evidence and are intentionally not claimed before the task branch is committed,
packaged, reviewed, and integrated.

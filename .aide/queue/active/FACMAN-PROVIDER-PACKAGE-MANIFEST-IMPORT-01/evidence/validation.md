# Validation

- Importer fixtures: 6 tests pass, covering byte-identical projection and
  negative source, ref, tree, version, ABI, state-format, contract, header,
  profile, matrix, stale-surface, and artifact controls.
- Real installed provider: ULK `b89d8d635601cf85bfd9d3c393fc56b91abfd24c`
  Windows static package accepted from its actual installed bytes; manifest
  SHA-256 `b3d315fbc2ebc8176976a0b4a2773d30067e9a15342a1e981bbd5aa93f842fc4`.
- Focused Python matrix: 61 tests pass across the importer, provider modes,
  adoption assertions, reconciliation, release compiler projections, and
  schema evidence.
- Schema validation: 346 schemas pass.
- Source format, structure policy, generated metadata, provider reconciliation,
  and release resolution pass.
- A clean canonical sibling layout at the exact protected FacMan, ULK, and USK
  source identities passes `tools/strict_check.py`.
- The focused PR #163 presentation executable builds with MSVC 19.51.36252.0,
  warnings-as-errors, and passes both with protected ULK `09f0639` and the
  non-adopting ULK 1.9.1 conformance canary `b89d8d6`.

Hosted qualification and integration remain pending. No ULK task SHA was
written to a tracked FacMan release input.

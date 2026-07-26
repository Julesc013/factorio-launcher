# Validation

Local validation is complete for the WorkUnit tree based on FacMan parent
`31264a99b428c2d34d9f21a39f0878b1eb75775a`, Universal Launcher
`fbb0cc87a14e8e4b26d74088a791dc83ebd4337d`, and Universal Setup
`3f8489275077347c2918f3bb03614ec6431362ff`.

- External TUI-off fast graph: 18/18 native tests passed.
- External TUI-on fast graph: 19/19 native tests passed.
- Fast Python graph observed during both configuration proofs: 31/31 passed.
- Full external TUI-on native matrix: 53/53 passed.
- Final Python promotion matrix: 514/514 passed with four classified skips.
- Required blocked skips: 0.
- Unknown skips: 0.
- Optional skips: 2.
- Unsupported platform-feature skips: 2.
- Promotion gate: pass.
- Obligation evidence SHA-256:
  `3f6eef304a66dc5714ebfa979261f67a913780329d141d3730ce23846471964e`.
- Generated build identity read-only probe: pass; no workspace was created.
- `python -B tools/project_state.py`: pass.
- `python -B tools/strict_check.py`: pass, 296 schemas.
- `python -B .aide/scripts/aide_lite.py test`: pass.
- `git diff --check`: pass, with line-ending conversion notices only.

Hosted validation on PR 76 exposed two portability defects in committed head
`95c73abaed291c4d19f35ee8bd1cb300061593b8`:

- archived `.ps1` evidence used a Windows-byte hash instead of the declared
  canonical-LF hash;
- the macOS job did not export its non-default native build root to the
  promotion obligation runner.

The repair canonicalizes PowerShell evidence line endings, updates the archived
index, binds the macOS native root, and adds regression/static CI coverage.
Focused AIDE compaction, CI proof, and obligation tests pass (14/14);
`tools/strict_check.py` and the portable AIDE suite pass after the repair.

Hosted validation remains pending for the repaired exact head. No Factorio
process, WPR capture, permit issuance, route promotion, or product execution
occurred.

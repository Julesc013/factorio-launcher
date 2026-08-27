# Validation

The following validations passed on Windows x64 with the pinned Universal
Launcher Kit revision `5479939ca5cbc9ee0f901608a92012778b4752ae` and Universal
Setup Kit revision `d2a2aae7e61c47035c92334b0522143b4fea3880`:

- Static native Debug: configure, build, and CTest `39/39`.
- Static native Release: configure, build, and CTest `39/39`.
- Shared native Debug: configure, build, and CTest `39/39`.
- Shared native Release: configure, build, and CTest `39/39`, including explicit
  `ulk_shared`, `usk_shared`, and `flb_factorio_shared` targets.
- WinForms Release x64: build completed with zero warnings and zero errors.
- Exhaustive Python suite: `1260` tests passed with `9` expected skips, including
  strict, package/runtime, WinForms transport, workspace, and provider checks.
- Focused regression suite: `117` tests passed.
- AIDE Lite portable validation passed.
- Strict, source-format, structure, version-truth, plan, project-state,
  release-programme, package-manifest, source-closure, and historical-alpha
  checks passed.
- Read-only Factorio version/help qualification passed for F100 through F210;
  the sanitized evidence contains no absolute installation paths or raw output.

Pre-closeout clean-source construction and verification passed for all three
literal 4.0.0 archives. Each qualification archive embeds source revision
`7c2cfbc469a2d3cee537d6b6ce4a12fadfb64ffd`, both exact provider revisions,
`source_dirty=false`, its expected profile and entrypoints, and an internal
SHA-256 manifest. `facman package verify --json` returned `status=pass` and
`integrity=sha256_consistent` for all three package roots with zero effects:

- `facman-4.0.0-windows-cli-x64-portable.zip`:
  `173d57eea9fbd3a8fa43bf47f2439d1c7585456ea4010ddfd3cb0c012b6bca28`
- `facman-4.0.0-windows-tui-x64-portable.zip`:
  `4b9ea92ed610d801d8f88a9e435e16bc26dec49773148afb2d7a22f4d039f096`
- `FacMan-4.0.0-windows-x64-portable.zip`:
  `6215bee58e40275c00887b133a56b82d34174c7215eb7dd31e3cc9fe2b073ee9`

The source branch was clean during construction, archive hashes match their
provenance sidecars, and a synthetic merge tree against local `main` completed
without conflicts. The merge-ready archives are rebuilt after the evidence-only
closeout commit; their exact source revision and hashes live in the co-located
provenance sidecars and the out-of-tree final-distribution receipt. Actual merge
authority remains outside this work unit.

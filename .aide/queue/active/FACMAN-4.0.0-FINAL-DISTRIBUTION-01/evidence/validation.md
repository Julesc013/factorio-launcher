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

Clean-source construction and verification of the three literal 4.0.0 archives
is the final promotion step and will be recorded here after the source commit is
fixed.


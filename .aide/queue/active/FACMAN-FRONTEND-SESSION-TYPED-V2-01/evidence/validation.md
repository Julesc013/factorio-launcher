# Validation

- Visual Studio 18 2026 static source-provider Debug and Release builds: PASS
  with warnings as errors and exact canonical ULK/USK provider pins.
- Canonical static CTest: 39 of 39 PASS in Debug and 39 of 39 PASS in Release.
- Canonical shared-provider WinForms CTest: 39 of 39 PASS in Debug and 39 of
  39 PASS in Release, including explicit ULK, USK, and Factorio binding DLLs.
- Typed frontend and identity focus: `facman_frontend_session_smoke`,
  `facman_client_smoke`, `facman_presentation_service_smoke`, and
  `fl_json_core_smoke`: PASS.
- Machine stdio transport suite: 6 of 6 PASS, including opaque Unicode/quoted
  v1 request IDs and exact v2 request/operation/attempt correlation.
- Contract compiler suite: 7 of 7 PASS with deterministic generated C++, C#,
  Python, bundle, and documentation output.
- Canonical schema validation: PASS for 382 schemas.
- Release WinForms x64 build: PASS with zero warnings and zero errors; the
  transport hardening harness passed 38 cases, and the command-client and C1
  shell checks passed.
- Windows built-package proof: 21 tests completed with PASS and one explicit
  optional non-Windows-generic profile skip; the CLI, TUI, canonical v2, and
  shared WinForms package classes all passed.
- Repository-wide Python discovery: 1,254 tests PASS with 31 explicit skips.
- Final strict governance validation: PASS, including 382 schemas, 127 command
  contracts, 244 refusal codes, executable cross-frontend parity, exact
  workspace locks, and the F100/F110/F200/F210 target contract.

The frontend task neither launches Factorio nor authorizes route execution.

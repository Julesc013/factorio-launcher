# Validation

- PASS: source commit `1b962531f1d386294b44c2230c230c9f66ad2fcc` is an ancestor of protected `dev@a158a6aa6eae947832fdd16101531ac122f7a3a6`, tree `f47600447ae36b67e35d077fa05e94817f506a8d`.
- PASS: the exact current C++ source was rebuilt in the existing owned Windows Debug root with Visual Studio 18 2026 and the pinned clean ULK `5479939ca5cbc9ee0f901608a92012778b4752ae` and USK `d2a2aae7e61c47035c92334b0522143b4fea3880` sources.
- PASS: `ctest --test-dir <owned_build_root> -C Debug --output-on-failure -R '^(facman_client_smoke|facman_terminal_capabilities_smoke)$'` ran 2/2 tests.
- PASS: the executable-bound machine transport, terminal frontend, TUI product, and cross-frontend conformance suites ran 37/37 tests.
- PASS: the Windows ConPTY suite ran 2/2 applicable tests; three POSIX PTY tests reported `not_applicable` on Windows.
- PASS: client boundary, architecture fitness, source format, canonical plan views, project state, and the complete portable AIDE Lite suite.
- ACCEPT: a non-authoring GPT-5.6 Terra review found the transport implementation already integrated and identified the `NO_COLOR` documentation contradiction corrected by this checkpoint. This is model-based technical review, not human acceptance.

The current machine-readable record is `terminal-contract-current-dev-validation.v1.json`; the immutable original source review remains `terminal-process-contract-source-review.v1.json`. The first build and Python invocations used incorrect target/import forms and are retained in the receipt; their corrected commands passed. Protected checks for this documentation/lifecycle checkpoint remain pending.

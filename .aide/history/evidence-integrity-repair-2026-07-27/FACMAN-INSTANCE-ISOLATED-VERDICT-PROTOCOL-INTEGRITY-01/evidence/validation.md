# Validation

WorkUnit: `FACMAN-INSTANCE-ISOLATED-VERDICT-PROTOCOL-INTEGRITY-01`

- Focused Python protocol, preflight, evidence, queue, and project-state tests: 68 passed; 2 platform-unsupported symlink tests skipped.
- Native verdict-harness protocol tests: 5 passed, including canonical evidence, privilege separation, route binding, recomputed exact-plan approval, and Windows execution-state lease acquisition/release.
- Full local promotion validation: 56 native tests and 541 Python tests passed.
- Promotion obligation result: 0 errors, 0 failures, 0 required-blocked skips, 0 unknown skips, 7 optional skips, and 2 unsupported symlink skips.
- Strict validation: passed with exact pinned Universal Launcher and Universal Setup worktrees.
- Project-state generation and validation: passed.
- AIDE queue and target-truth validation: passed.
- Portable AIDE Lite validation: passed.
- `git diff --check`: passed.

No permit was issued. No Factorio process, observer capture, baseline, human
revalidation evidence, route promotion, policy change, Setup mutation, signing,
or publication occurred.

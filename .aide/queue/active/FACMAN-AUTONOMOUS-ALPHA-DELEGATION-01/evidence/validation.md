# Validation

Result: **PASS for the bounded alpha-tag review candidate.** This is local
engineering evidence, not protected integration, a tag, publication, support,
or a public `0.1` completion verdict.

## Exact source and providers

- FacMan task base: `e73d778173be283d47925fa055ba1aae7b82fb28`
  (`origin/dev` at validation start).
- The definitive full run followed all implementation and generated-file
  changes; only this evidence count and later commit metadata followed it.
- Universal Launcher clean detached revision/tree:
  `5479939ca5cbc9ee0f901608a92012778b4752ae` /
  `7728e4d415539a0f24e6f17aa7d22be00cc99d80`.
- Universal Setup clean detached revision/tree:
  `d2a2aae7e61c47035c92334b0522143b4fea3880` /
  `291d63214cdd0cd3d15c809de5744ee3514fb2b2`.
- The primary checkout remained clean on `dev...origin/dev`.

## Tests and validators

- Focused alpha tag/receipt, release programme, CI proof, source/publication,
  branch-policy, plan, project-state, and AIDE suite: PASS, 119 tests.
- Full Python discovery with exact provider roots: PASS, 1,227 tests with 10
  classified skips. This includes packaged-runtime, WinForms transport,
  frontend, provider, release, security, accessibility-packet, and AIDE tests.
- Schema validation: PASS, 367 schemas.
- Standalone `tools/strict_check.py`: PASS, including `alpha-tag-policy`,
  release-programme, CI-proof, source-format, package/profile/layout/runtime,
  provenance, security, accessibility, route, source-closure, and generated
  truth checks.
- Project state `--validate`, plan views `--check`, generated metadata
  `--check`, and `git diff --check`: PASS.
- AIDE Lite portable validation: PASS.
- The exact Windows ConPTY regression test passed three consecutive isolated
  runs after removing inherited `TERM=dumb`/`NO_COLOR` only for the child PTY
  under test and restoring the host environment afterward.

## Native and package-runtime proof

- CMake 4.2.3 / Visual Studio 18 2026 / Windows SDK 10.0.26100.0, MSVC Debug,
  source-mode static providers, CLI and TUI enabled, GUI disabled, tests
  enabled, setup enabled, warnings-as-errors enabled, and explicit `/EHsc`:
  configure and build PASS.
- Native CTest: PASS, 38/38. Labels include contract, integration, security,
  provider, package-runtime, installed-SDK, filesystem, frontend, and platform.
- A first reconfigure invocation included an unnecessary `-A x64` against the
  existing generator cache and was correctly refused before generation; the
  subsequent cache-consistent invocation above is the accepted proof.

## Live GitHub read-only checks

- Execution identity: `BLACKGLASS-WIN1\Jules`; GitHub account: `Julesc013`.
- Protected `dev` effective required-status-check rule exactly contained the 11
  policy check contexts, GitHub Actions app ID `15368`, and strict up-to-date
  enforcement.
- At `2026-08-26T22:38:53Z`, repository ruleset observation returned only
  active branch ruleset ID `20445007`; there was no tag-target ruleset.
  Consequently the new tag gate refuses effects until the separately reviewed
  no-bypass/no-exclusion update-and-deletion ruleset exists.

## Tool identities

- CPython 3.14.7
- CMake 4.2.3
- Git 2.53.0.windows.1
- GitHub CLI 2.96.0

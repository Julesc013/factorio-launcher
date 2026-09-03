# Validation

Result: PASS for active-release-view consolidation and the complete local
developer promotion-equivalent matrix. This is engineering evidence only and
grants no human, protected-integration, signing, tagging, publication, or
support authority.

## Active-view and affected validation

`tools/active_release_view_check.py` passed with exactly:

- three product profiles: Windows x64 reference, macOS Intel x64 selected
  preview, and Linux x64 selected preview;
- two selected preview profiles; and
- eight canonical assets: six product packages, `SHA256SUMS`, and consolidated
  evidence.

The validator cross-checked profile, package, producer, support, distribution,
update, artifact, release-index, and historical-receipt views. Its regression
suite includes fail-closed negative controls for legacy-current leakage,
undeclared previews, and cross-view mismatches.

The affected matrix passed 41/41 native tests and 171 Python tests with two
declared skips. Dedicated generated-metadata, source-format,
release-identity, source-closure, final-Alpha.5-closeout, engineering-quality,
project-state, strict, and AIDE Lite checks also passed.

## Canonical-dev restack requalification

After the predecessor merged, a normal forward merge incorporated canonical
`dev` commit `f99d96e002f5af519824942a1f8b74bcc26d96f8` without changing the
consolidation tree. The first deterministic affected run then failed closed
before test execution because the configured `facman_content_foundation_smoke`
CTest case was missing from the fast-test impact policy. The policy now lists
that target both globally and for `runtime/factorio/`, and a regression test
proves that content-foundation changes select it.

The repaired affected gate passed all three selected native tests and all 15
selected Python tests; its four skips were classified and no required or
unknown obligation was skipped. The complete developer verification below was
then rerun from the restacked source and is the authoritative local result.

After the canonical base and restack receipt were bound into the WorkUnit, the
final affected gate expanded as intended and passed all four selected native
tests and all 90 selected Python tests. Its one optional installed-component
skip was classified; required and unknown skip counts remained zero. All 13
selected strict validators passed.

## Full promotion-equivalent validation

The final authoritative managed command was:

```text
py -3 tools/dev.py verify-all developer
```

It exited 0 and completed:

- Debug native configure/build and 41/41 CTest cases;
- Release native source-static configure/build;
- Release product-shared configure/build and package-proof roots;
- WinForms .NET Framework 4.8 x64 Release with 0 warnings and 0 errors;
- 1,478 Python tests with 0 failures and 0 errors; and
- the final strict validator pass, including all 402 registered schemas.

The nine skips were fully classified: two optional, five unsupported because
the Windows token lacks symlink privilege, and two not applicable POSIX PTY
cases covered by a separate Windows ConPTY lane. Required-blocked and unknown
skip counts were both zero.

No Factorio execution, live setup/install mutation, human verdict, signing,
notarization, tagging, publication, support promotion, protected-setting
change, or protected-branch merge was performed.

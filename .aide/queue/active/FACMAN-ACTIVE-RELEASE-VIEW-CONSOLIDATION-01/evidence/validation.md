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
- 1,477 Python tests with 0 failures and 0 errors; and
- the final strict validator pass, including all 402 registered schemas.

The nine skips were fully classified: two optional, five unsupported because
the Windows token lacks symlink privilege, and two not applicable POSIX PTY
cases covered by a separate Windows ConPTY lane. Required-blocked and unknown
skip counts were both zero.

No Factorio execution, live setup/install mutation, human verdict, signing,
notarization, tagging, publication, support promotion, protected-setting
change, or protected-branch merge was performed.

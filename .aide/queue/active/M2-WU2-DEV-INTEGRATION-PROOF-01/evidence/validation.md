<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

## Integration identities

| Evidence | Identity |
| --- | --- |
| reviewed PR | `#14` |
| PR head | `f051731b80b51cac2d192ddb39535485f2a9c431` |
| preserved `dev` merge | `747b4442cf228561de9fa15834bf78b0dad72f23` |
| exact-`dev` CI | `29326004461` |
| exact-`dev` CodeQL | `29326004230` |
| exact-`dev` security policy | `29326004219` |

PR #14 merged with a merge commit, preserving the complete WU2 series rather
than squashing it. Its exact-head push and PR matrices were green before merge.

## Exact-dev results

- Linux native, Release, sanitizer, archive corpus, bounded fuzz, CLI/TUI
  package, and zero-skip package proof: PASS;
- Linux critical-module coverage: PASS;
- Windows Debug/Release native, Python, WinForms, selected package,
  reproducibility, TUI, legacy WinForms, and zero-skip package proof: PASS;
- macOS Intel native, Python, strict, CLI/TUI package, and archive core: PASS;
- AppKit compile: PASS;
- CodeQL C/C++, C#, and Python: PASS;
- security policy: PASS.

The workflow runs all bind `headSha`
`747b4442cf228561de9fa15834bf78b0dad72f23` and event `push` on `dev`.

## Authority result

This record proves reviewed `dev` integration only. The human M2 verdict
remains `pending`; ordinary managed-portable apply, real Factorio archive
acceptance, and `recovery.apply` remain unavailable. It makes no execution,
H1, Safe beta, signing, publication, or publisher-authenticity inference.

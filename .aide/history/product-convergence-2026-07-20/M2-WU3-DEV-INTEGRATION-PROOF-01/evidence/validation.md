<!-- SPDX-FileCopyrightText: 2026 Jules C -->
<!-- SPDX-License-Identifier: MIT -->

# Validation

## Integration identities

| Evidence | Identity |
| --- | --- |
| reviewed PR | `#16` |
| PR head | `5f93f42f97089ae367e718d3466f4421abf43625` |
| preserved `dev` merge | `a8b298a35cd1587cea566886b5a3891153a2b7f2` |
| shared task/merge tree | `b634c5b35080ae48d6b19acbc5b3ddbc1564ca9a` |
| exact-`dev` CI | `29332570822` |
| exact-`dev` CodeQL | `29332570777` |
| exact-`dev` security policy | `29332570776` |

PR #16 merged with a merge commit and preserved the complete WU3 series. Its
exact-head push and pull-request matrices were green before merge.

## Exact-dev results

- Linux native, Release, sanitizer, archive corpus, bounded fuzz, coverage,
  CLI/TUI package, and zero-skip package proof: PASS;
- Windows Debug/Release native, Python, WinForms, selected package,
  reproducibility, TUI, legacy WinForms, and zero-skip package proof: PASS;
- macOS Intel native, Python, strict, CLI/TUI package, and archive core: PASS;
- AppKit compile: PASS;
- CodeQL C/C++, C#, and Python: PASS;
- security policy: PASS.

All runs bind `headSha` `a8b298a35cd1587cea566886b5a3891153a2b7f2`
and event `push` on `dev`.

## Authority result

This proves reviewed WU3 `dev` integration only. The human M2 verdict remains
`pending`; ordinary managed-portable apply, real Factorio archive acceptance,
and `recovery.apply` remain unavailable. It makes no execution, H1, Safe beta,
signing, publication, or publisher-authenticity inference.

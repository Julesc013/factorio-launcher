# Validation

Status: LOCAL PASS; HOSTED REVIEW PENDING.

No Factorio process, WPR capture, permit, human verdict, route acceptance or
authority promotion is allowed in this WorkUnit.

Observed local results on Windows x64:

- focused producer/coordinator Python suite: 8 of 8 passed;
- complete supported Python suite: 527 passed with 9 expected
  optional/platform skips;
- fresh Visual Studio 18 2026 x64 native graph: 55 of 55 CTests passed;
- strict validation: 300 schemas and every policy, security, package, release
  and three-repository lock check passed;
- portable AIDE Lite validation: PASS;
- both frozen policy digests remained exact.

The fresh native build used MSVC `19.51.36248.0`, Windows SDK
`10.0.26100.0`, and an initially absent task-owned build root under the local
temporary directory.

The required-package wrapper correctly refused to operate while the source
checkout was dirty before commit. Its clean exact-head proof remains a hosted
review obligation; that refusal was not bypassed.

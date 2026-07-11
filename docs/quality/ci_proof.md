# CI Proof Lanes

CI mirrors the bounded proof rather than implying release readiness.

- `linux-native` builds the native core and sibling repositories, runs CTest,
  the Python suite, strict checks, portable compatibility packages, and the
  zero-skip `linux_portable_cli_x64` tarball proof. The proof records ELF,
  glibc/toolchain, dynamic dependency, relocation, integrity, and runtime
  evidence and uploads the unsigned, unpublished artifact and report.
- `windows-native-package` builds the native core on Windows, runs CTest and
  the Python suite, compiles WinForms, and runs the selected
  `windows_portable_cli_x64` package proof through a zero-skip wrapper.
- `macos-native-cli` builds the complete native core on `macos-15-intel`, runs
  CTest, the portable Python suite and strict checks, then runs the zero-skip
  `macos_portable_cli_x64` tarball proof. It records Mach-O architecture,
  deployment target, SDK/toolchain, system linkage, relocation, integrity,
  provenance, and runtime evidence.
- `appkit-compile` remains an independent legacy shell compile-only lane. It is
  not an AppKit runtime or app-package claim.
- `security-policy` describes the current policy-only security check honestly.
- `release-policy` validates unpublished release contracts and does not invoke
  the retired Python-package build path or publish artifacts.

`tools/ci_proof_check.py` makes these anchors part of strict validation. Future
changes may replace the commands, but they must preserve equivalent evidence
and update the checker in the same reviewed change.

Each selected package runner refuses the wrong host/architecture, any test
failure, and any skipped required package test. The Windows runner also
refuses a dirty checkout. Ordinary platform-specific skips elsewhere in the
cross-platform test corpus do not satisfy or invalidate any target-specific
gate.

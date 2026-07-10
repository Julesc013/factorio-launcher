# CI Proof Lanes

CI mirrors the bounded proof rather than implying release readiness.

- `linux-native` builds the native core and sibling repositories, runs CTest,
  the Python suite, strict checks, and portable compatibility packages.
- `windows-native-package` builds the native core on Windows, runs CTest and
  the Python suite, compiles WinForms, and runs the selected
  `windows_portable_cli_x64` package proof through a zero-skip wrapper.
- `appkit-compile` remains an explicit `macos-15-intel` legacy shell compile lane. It
  is not a macOS native-core or package claim.
- `security-policy` describes the current policy-only security check honestly.
- `release-policy` validates unpublished release contracts and does not invoke
  the retired Python-package build path or publish artifacts.

`tools/ci_proof_check.py` makes these anchors part of strict validation. Future
changes may replace the commands, but they must preserve equivalent evidence
and update the checker in the same reviewed change.

The selected package runner refuses a dirty checkout, a non-Windows host, any
test failure, and any skipped required package test. Ordinary platform-specific
skips elsewhere in the cross-platform test corpus do not satisfy or invalidate
that target-specific gate.

# R3.4 closeout remaining risks

- Fresh Ubuntu 24.04 sanitizer, libFuzzer, coverage, clang-tidy, and package
  evidence is not available for the pinned R3.4 revision.
- Fresh macOS 15 Intel native/package and AppKit compile evidence is not
  available for the pinned R3.4 revision.
- The local MinGW compiler has no sanitizer runtimes; its executables are not a
  supported runtime lane and some CTests stalled.
- Universal Launcher and Universal Setup licensing remains `NOASSERTION`
  pending an operator decision.
- Artifacts are unsigned and unpublished. Hashes and adjacent provenance prove
  consistency, not publisher authenticity.
- Real Factorio isolation still requires an operator verdict. No automated
  result substitutes for that human acceptance.

The target-runner gaps block cross-platform R3.4 promotion, but not the honest
recording of the locally completed architecture implementation.

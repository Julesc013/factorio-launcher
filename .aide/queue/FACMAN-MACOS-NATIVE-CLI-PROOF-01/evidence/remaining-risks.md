# Remaining Risks

- Intel-runner proof does not cover Apple Silicon or a universal binary.
- The chosen deployment target and recorded system libraries bound the package
  claim; broader macOS-version compatibility requires separate target evidence.
- AppKit remains compile-only. No `.app` bundle execution, signing,
  notarization, or publisher authenticity is claimed.

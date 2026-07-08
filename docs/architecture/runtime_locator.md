# Runtime Locator

The runtime locator hides package-layout differences from frontends and kernels.

It answers:

- package root
- schema directory
- data/template directory
- bundled tool directory
- native library directory
- daemon path
- optional extracted runtime path

Supported layouts:

- developer checkout
- Windows portable ZIP
- Windows installer
- Windows single-EXE extracted runtime
- macOS `.app`
- Linux AppImage
- Linux legacy tarball

Runtime locator code lives under `source/runtime/`.

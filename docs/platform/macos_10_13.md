# macOS 10.13 Support Policy

macOS GUI target:

```text
GUI: AppKit
Language: Objective-C and Objective-C++
Legacy deployment target: macOS 10.13
Legacy architecture: x86_64
Interop: C ABI or JSON-RPC over local process/socket
```

Pin a toolchain that still supports `MACOSX_DEPLOYMENT_TARGET=10.13`. Current
Xcode support matrices should be treated as a build input, not a permanent
assumption. If modern Xcode raises deployment targets, keep a legacy Xcode
lane for the 10.13 build.

Avoid requiring SwiftUI, modern-only AppKit APIs, arm64-only binaries, or a
new deployment target default for the legacy artifact.

The AppKit adapter declares availability for symbols, dark appearance,
vibrancy, toolbar/navigation features, and effects. Unsupported features fall
back to standard controls, system fonts/colors, bundled template images, and
ordinary tables/outlines without changing workflow semantics. See
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).

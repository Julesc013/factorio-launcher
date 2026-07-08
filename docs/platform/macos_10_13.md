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

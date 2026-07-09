# macOS Targets

```text
macos_legacy_appkit
  GUI: AppKit
  Language: Objective-C / Objective-C++
  Role: legacy Intel macOS lane with pinned legacy toolchain

macos_modern_swiftui
  GUI: SwiftUI
  Language: Swift
  Role: modern macOS x64/arm64 lane
```

Both lanes keep Factorio-specific behavior in the native backend and present
the same command graph as CLI, TUI, and daemon frontends.

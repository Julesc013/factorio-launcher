# macOS Targets

```text
macos_legacy_appkit
  GUI: AppKit
  Language: Objective-C / Objective-C++
  Shell profile: classic.macos.appkit
  Design authority: Apple HIG for macOS
  Role: classic Intel macOS lane with pinned compatibility toolchain

macos_modern_swiftui
  GUI: SwiftUI
  Language: Swift
  Shell profile: modern.macos.swiftui
  Design authority: Apple HIG for macOS
  Role: modern adaptive macOS x64/arm64 lane
```

Both lanes keep Factorio-specific behavior in the native backend and present
the same command graph as the `facman` JSON, human CLI, and TUI modes. A daemon
is not admitted to the product package.

AppKit and SwiftUI are frameworks, not separate Apple design languages.
Settings, global menus, shortcuts, windowing, tables, sidebars, sheets, and
capability fallbacks follow macOS conventions. See
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).

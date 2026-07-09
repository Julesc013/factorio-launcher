# Frontend Targets

Every frontend presents the same command graph. No frontend is the backend for
another frontend.

| Lane | Path | Role |
| --- | --- | --- |
| CLI | `apps/cli/` | scriptable console frontend |
| TUI | `apps/tui/` | console UI frontend |
| Daemon | `apps/daemon/` | local job/IPC host |
| Windows WinForms | `apps/gui/windows/winforms/` | legacy Windows GUI |
| Windows WinUI | `apps/gui/windows/winui/` | modern Windows GUI |
| macOS AppKit | `apps/gui/macos/appkit/` | legacy macOS GUI |
| macOS SwiftUI | `apps/gui/macos/swiftui/` | modern macOS GUI |
| Linux GTK | `apps/gui/linux/gtk/` | X11-first Linux GUI |
| Linux Qt | `apps/gui/linux/qt/` | Wayland-first Linux GUI |

Distribution packages may include CLI, TUI, daemon, and GUI binaries together.
Individual executables remain purpose-built shells.

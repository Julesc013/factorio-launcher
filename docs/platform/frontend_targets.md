# Frontend Targets

Every frontend presents the same command graph. No frontend is the backend for
another frontend.

| Lane | Path | Role |
| --- | --- | --- |
| CLI | `apps/cli/` | scriptable console frontend |
| TUI | `apps/tui/` | console UI frontend |
| Daemon | `apps/daemon/` | unavailable placeholder for a future local job/IPC host |
| Windows WinForms | `apps/gui/windows/winforms/` | classic Windows desktop shell |
| Windows WinUI 3 | `apps/gui/windows/winui/` | modern Fluent Windows shell |
| macOS AppKit | `apps/gui/macos/appkit/` | classic native Mac shell |
| macOS SwiftUI | `apps/gui/macos/swiftui/` | modern adaptive Mac shell |
| Linux GTK 3 | `apps/gui/linux/gtk/` | classic X11-first cross-desktop shell |
| Linux Qt 6/Kirigami | `apps/gui/linux/qt/` | modern KDE/Wayland adaptive shell |

Distribution packages may include proven CLI, TUI, and GUI binaries together.
The daemon placeholder does not become package or support proof merely because
its target compiles. Individual executables remain purpose-built shells.

Proof status is tracked separately from lane existence. See
[`docs/quality/frontend_proof_levels.md`](../quality/frontend_proof_levels.md)
for the current source-static, compile, runtime-smoke, and package-smoke status
of each frontend.

“Classic” describes shell and dependency strategy, not poor design or obsolete
interaction. “Modern” describes the adaptive projection, not greater product
authority. Framework, HIG, appearance, capability, accessibility, and
qualification rules are defined in
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).

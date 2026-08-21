# Frontend Targets

Every frontend presents the same command graph. No frontend is the backend for
another frontend.

| Lane | Path | Role |
| --- | --- | --- |
| Terminal host | `apps/cli/` | `facman` router for normative CLI JSON, bounded human CLI, and explicit TUI mode |
| TUI module | `apps/tui/` | same-binary task UI and generated Advanced command surface |
| Daemon | `apps/daemon/` | unavailable placeholder for a future local job/IPC host |
| Windows WinForms | `apps/gui/windows/winforms/` | classic Windows desktop shell |
| Windows WinUI 3 | `apps/gui/windows/winui/` | modern Fluent Windows shell |
| macOS AppKit | `apps/gui/macos/appkit/` | classic native Mac shell |
| macOS SwiftUI | `apps/gui/macos/swiftui/` | modern adaptive Mac shell |
| Linux GTK 3 | `apps/gui/linux/gtk/` | classic X11-first cross-desktop shell |
| Qt 6 Widgets | `apps/gui/qt/widgets/` | optional separately admitted traditional cross-platform Qt shell |
| Linux Qt 6/Kirigami | `apps/gui/linux/qt/quick/` | optional separately admitted KDE/Wayland adaptive shell |

Distribution packages contain one required `facman` terminal binary and may
include a proven native GUI binary.
The daemon placeholder does not become package or support proof merely because
its target compiles. Native GUI executables remain purpose-built shells.

Proof status is tracked separately from lane existence. See
[`docs/quality/frontend_proof_levels.md`](../quality/frontend_proof_levels.md)
for the current source-static, compile, runtime-smoke, and package-smoke status
of each frontend.

“Classic” describes shell and dependency strategy, not poor design or obsolete
interaction. “Modern” describes the adaptive projection, not greater product
authority. Framework, HIG, appearance, capability, accessibility, and
qualification rules are defined in
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).

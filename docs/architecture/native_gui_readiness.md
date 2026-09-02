# Native GUI readiness

FacMan has a 1.0-shaped presentation architecture at alpha.5 maturity. Native
shells are projections of one command and presentation model; they are not
independent products or policy authorities.

## Current lanes

| Lane | Current evidence | Remaining boundary |
| --- | --- | --- |
| WinForms, Windows 10/11 x64, .NET Framework 4.8 | Reference shell; exact-candidate machine-qualified in run `33603385303` attempt 1 | Human install, keyboard/accessibility/DPI, packaged performance, real Play, and support |
| GTK3, Ubuntu 24.04 x64/X11 | Exact-candidate machine-qualified semantic preview | Typed presentation parity, human install/accessibility/performance, wider distributions/Wayland, and support |
| AppKit, macOS 13+ Intel | Exact-candidate machine-qualified semantic preview | Typed presentation parity, human install/accessibility/performance, Apple Silicon, signing/notarization, and support |
| Qt6 | Scaffold only | Separate post-beta admission, implementation, and qualification |
| WinUI | Placeholder boundary only | Separate post-beta admission, implementation, and qualification |
| SwiftUI | Placeholder boundary only | Separate post-beta admission, implementation, and qualification |

The exact candidate source is revision
`4683ecd9a1b9ead5eb84be152760d12583da0f0e`, tree
`c07938618bc0f533fd12756cba123f54b8592048`; the non-authorizing receipt is
`release/index/alpha5_final_candidate_closeout.v1.toml`. No human verdict,
publication, or support claim follows from that machine result, and later
revisions need a fresh candidate run.

Provider roots remain:

- `apps/gui/windows/winforms`
- `apps/gui/windows/winui`
- `apps/gui/macos/appkit`
- `apps/gui/macos/swiftui`
- `apps/gui/linux/gtk`
- `apps/gui/linux/qt`

## Boundary

Each GUI is a command/presentation client over the direct or bounded-process
transport. There is no public daemon/service transport. Product discovery,
readiness, managed-install policy, mod resolution, save import/export,
session/Last Run truth, and server execution remain backend responsibilities.
Universal Setup alone owns admitted installed-software mutation.

`tools/gui_surface_check.py` validates that providers retain a command-client
surface and contain no direct process-execution or setup/mod-portal mutation
markers.

```text
CLI / TUI / WinForms / AppKit / GTK
  -> direct or bounded-process command/presentation boundary
  -> FacMan application and domain core
  -> Universal Launcher for generic operation/session lifecycle
  -> Universal Setup only for admitted installed-software mutation

Qt6 scaffold / WinUI placeholder / SwiftUI placeholder
  -> post-beta admission; no current release lane
```

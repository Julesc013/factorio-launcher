# Support Policy

FacMan support is lane-based.

## Policy

- Windows legacy is WinForms over .NET Framework 4.8 and is best-effort legacy
  support.
- Windows modern is WinUI and is a future primary modern lane.
- macOS legacy is AppKit and is the first macOS native lane.
- macOS modern is SwiftUI and follows after AppKit proof.
- Linux X11 legacy is GTK 3 and is the first Linux GUI lane.
- Linux Wayland modern is Qt 6 and follows after GTK proof.

Exact OS floors must be verified against current platform toolchain docs before
release publication. Repository contracts can name target lanes, but they do
not replace platform release validation.

## Deferred Claims

The current repository contracts do not claim:

- signed Windows installers
- notarized macOS installers
- AppImage compatibility across every distribution
- package-manager publication
- delta updates
- managed Factorio install mutation
- self-update apply

Those claims require later release evidence and should be added only after the
matching package verification passes.

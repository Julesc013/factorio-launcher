# Linux Targets

```text
linux_x11_gtk
  GUI: GTK 3
  Shell profile: classic.linux.gtk3
  Design authority: GTK 3 behavior plus selected general GNOME principles
  Role: X11-first cross-desktop compatibility lane

linux_wayland_qt
  GUI: Qt 6 Quick Controls + Kirigami
  Shell profile: modern.linux.qt6-kirigami
  Design authority: KDE HIG, Kirigami, and Qt Quick conventions
  Role: Wayland-first modern adaptive desktop lane

portable_cli
  GUI: none required
  Role: old distro, server, and minimal dependency lane
```

GTK and Qt packages may share CLI, TUI, daemon, contracts, content, and native
libraries. The backend must still run without GUI toolkit dependencies.

GTK 3 does not require a header bar and must preserve desktop-selected themes.
Qt 6 is not one design system; generic Fusion styling is not a KDE
qualification. See
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).

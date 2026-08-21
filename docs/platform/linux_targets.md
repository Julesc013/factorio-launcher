# Linux Targets

```text
linux_x11_gtk
  GUI: GTK 3
  Shell profile: classic.linux.gtk3
  Design authority: GTK 3 behavior plus selected general GNOME principles
  Role: X11-first cross-desktop compatibility lane

qt6_widgets
  GUI: Qt 6 Widgets
  Shell profile: primary.qt6-widgets
  Design authority: target desktop conventions plus Qt Widgets guidance
  Role: separately admitted traditional cross-platform Qt projection

linux_wayland_qt_quick
  GUI: Qt 6 Quick Controls + Kirigami
  Shell profile: modern.linux.qt6-kirigami
  Design authority: KDE HIG, Kirigami, and Qt Quick conventions
  Role: separately admitted Wayland-first adaptive KDE lane

portable_cli
  GUI: none required
  Role: old distro, server, and minimal dependency lane
```

GTK and Qt packages may share the `facman` CLI/TUI host, contracts, content,
and native libraries. A future local service is separately admitted. The
backend must still run without GUI toolkit dependencies.

GTK 3 does not require a header bar and must preserve desktop-selected themes.
Qt 6 is not one design system; generic Fusion styling is not a KDE
qualification. See
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).

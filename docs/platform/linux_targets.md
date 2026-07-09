# Linux Targets

```text
linux_x11_gtk
  GUI: GTK
  Role: X11-first compatibility desktop lane

linux_wayland_qt
  GUI: Qt
  Role: Wayland-first modern desktop lane

portable_cli
  GUI: none required
  Role: old distro, server, and minimal dependency lane
```

GTK and Qt packages may share CLI, TUI, daemon, contracts, content, and native
libraries. The backend must still run without GUI toolkit dependencies.

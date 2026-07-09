# Linux Wayland Qt Profile

Modern Linux desktop profile for Qt packages.

Expected posture:

- Qt frontend isolated under `apps/gui/linux/qt/`
- Wayland-first distribution lane
- native CLI/TUI/daemon helpers in the package
- shared runtime libraries, contracts, and content
- no GUI toolkit dependency in runtime or public ABI

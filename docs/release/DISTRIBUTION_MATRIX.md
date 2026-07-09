# Distribution Matrix

FacMan uses the same release classes on every platform, mapped to native
package formats where appropriate.

## Release Classes

```text
portable archive
user installer
system installer
offline bundle
update package
developer SDK or source package
```

The classes are semantic. File extensions differ by platform.

## Phase 1 Artifacts

The first useful release set is:

```text
facman-<version>-windows-winforms-x64-portable.zip
facman-<version>-windows-winforms-x64-setup.exe
facman-<version>-macos-appkit-x64.dmg
facman-<version>-linux-gtk-x64.tar.zst
facman-<version>-source.tar.gz
facman-<version>-checksums.txt
facman-<version>-release_manifest.json
```

These artifacts prove package shape before broad architecture coverage.

## Planned Lanes

Windows lanes:

```text
windows_legacy_winforms_x86
windows_legacy_winforms_x64
windows_modern_winui_x64
windows_modern_winui_arm64
```

macOS lanes:

```text
macos_legacy_appkit_x64
macos_modern_swiftui_universal2
```

Linux lanes:

```text
linux_x11_gtk_x86
linux_x11_gtk_x64
linux_wayland_qt_x64
linux_wayland_qt_arm64
```

Portable and support lanes:

```text
portable_cli
portable_full
source
offline_bundle
```

`release/profiles/profile_catalog.v1.toml` is the catalog for this matrix.
Only contract-backed profiles are listed in `release/index/release_index.v1.toml`
until their package manifests and validation evidence exist.

## Package Contents By Lane

GUI package lanes include CLI, TUI, daemon, and one GUI stack. CLI-only and
TUI-only packages remain smaller, but they still point back to the same command
surface contract.

Do not ship GTK and Qt in the same default Linux package. Do not ship WinForms
and WinUI in the same default Windows package. A combined package can be added
later as its own release profile.

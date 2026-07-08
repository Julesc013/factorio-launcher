# Packaging Model

FacMan ships as one seamless user-visible package per platform, not as one
giant executable internally.

Each package contains replaceable components:

- GUI frontend
- CLI frontend
- TUI frontend
- daemon / job runner
- universal launcher kernel
- universal setup kernel or setup adapter
- Factorio binding
- `contracts/schema/`
- `content/factorio/`
- platform helpers

The package may feel like one app to the user. Internally, components stay
separate so they can be debugged, replaced, backported, or omitted in legacy
profiles.

## Windows

The canonical Windows artifact is a portable ZIP:

```text
FacMan-<version>-windows-x64-portable.zip
  FacMan.exe
  facman.exe
  facman-tui.exe
  facmand.exe
  bin/
    ulk.dll
    usk.dll
    flb_factorio.dll
  content/
    factorio/
  contracts/
    schema/
  docs/
```

The installer is optional. The single EXE is only a bootstrapper and must
extract to a versioned `%LOCALAPPDATA%/FacMan/runtime/...` directory, never to
`%TEMP%` for normal execution.

## macOS

The macOS package is an `.app` bundle:

```text
FacMan.app/
  Contents/MacOS/
    FacMan
    facman
    facman-tui
    facmand
  Contents/Frameworks/
    libulk.dylib
    libusk.dylib
    libflb_factorio.dylib
  Contents/Resources/
    content/
      factorio/
    contracts/
      schema/
    docs/
```

Executables and dylibs do not live in `Contents/Resources`.

## Linux

Modern Linux GUI packages use AppImage. Old Linux targets use CLI/TUI tarballs
or source builds. GTK is the first Linux GUI frontend; Qt remains optional.

## Manifests

Versioned package manifests live under `release/packaging/`. They declare
component names, source targets, package destinations, architecture, hashes,
signature policy, extraction policy, runtime search path, and license notices.

`tools/package_check.py` enforces the packaging rules.

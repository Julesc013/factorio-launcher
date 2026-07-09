# Distribution Layout

Each distribution package should include the frontends and shared components
appropriate for its lane. That does not mean each executable implements every
frontend mode.

## Windows

```text
bin/
  FacMan.WinForms.exe or FacMan.WinUI.exe
  facman.exe
  facman-tui.exe
  facmand.exe
  flb_factorio.dll
  ulk.dll
  usk.dll
contracts/
content/
docs/
licenses/
```

## macOS

```text
FacMan.app/
  Contents/MacOS/
    FacMan
    facman
    facman-tui
    facmand
  Contents/Frameworks/
    libflb_factorio.dylib
    libulk.dylib
    libusk.dylib
  Contents/Resources/
    contracts/
    content/
    docs/
    licenses/
```

## Linux

```text
bin/
  facman
  facman-tui
  facman-gui-gtk or facman-gui-qt
  facmand
lib/
share/facman/
  contracts/
  content/
  docs/
  licenses/
```

Profile-specific packages can include one GUI stack. A larger combined package
can include more than one GUI later, but that is a release-profile decision.

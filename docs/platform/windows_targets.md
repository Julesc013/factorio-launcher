# Windows Targets

```text
windows_legacy_winforms
  GUI: WinForms
  Runtime: .NET Framework 4.8
  Role: Windows 7 SP1+ compatibility lane

windows_modern_winui
  GUI: WinUI
  Runtime: modern .NET desktop runtime
  Role: current Windows desktop lane
```

Both distributions include the native CLI, TUI, daemon, shared runtime
libraries, contracts, and content where supported. The GUI executable remains a
frontend, not a setup mutator or launcher backend.

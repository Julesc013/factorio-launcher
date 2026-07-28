# Windows Targets

```text
windows_legacy_winforms
  GUI: WinForms
  Runtime: .NET Framework 4.8
  Shell profile: classic.windows.winforms
  Design authority: Windows desktop and Win32 interaction conventions
  Role: Windows 7 SP1+ compatibility-oriented classic lane

windows_modern_winui
  GUI: WinUI 3
  Runtime: modern .NET desktop runtime
  Shell profile: modern.windows.winui
  Design authority: current Fluent and Windows app guidance
  Role: current adaptive Windows desktop lane
```

Both distributions include the native CLI, TUI, daemon, shared runtime
libraries, contracts, and content where supported. The GUI executable remains a
frontend, not a setup mutator or launcher backend.

WinForms uses responsive layout, DPI/font scaling, standard controls, system
fonts/colors, keyboard access, and System Native recovery. WinUI materials and
navigation are capability-gated and require solid/contrast fallbacks. See
[`docs/product/interface_design_system.md`](../product/interface_design_system.md).

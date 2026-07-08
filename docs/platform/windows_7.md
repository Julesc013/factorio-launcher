# Windows Support Policy

Windows GUI target:

```text
GUI: .NET Framework 4.8 WinForms
Minimum: Windows 7 SP1, best effort
Native target macro: _WIN32_WINNT=0x0601
IPC: named pipes
Distribution: portable ZIP first
```

The Windows 7 promise is compatibility-oriented, not a security guarantee.
Microsoft lists Windows 7 SP1 as compatible with .NET Framework 4.8, while also
noting that Windows 7 is out of support. .NET Framework support follows the
underlying Windows OS lifecycle.

Avoid:

- Windows 10-only APIs
- UWP
- WinUI
- .NET 5+
- .NET 6+
- .NET 8+
- MSIX-only packaging

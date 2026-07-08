# Win32 GUI Frontend

Target .NET Framework 4.8 and keep Windows 7 SP1 compatibility best-effort.
The GUI is a command graph client. It must not own install mutation, mod
resolution, or launch-plan generation.

The concrete legacy-compatible shell is WinForms, but the directory is named
`win32` so architecture refers to the platform provider rather than the toolkit.

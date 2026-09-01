# Distribution Matrix

This file records the immutable alpha.3 distribution. The version-current 0.1
candidate law is defined by `release/index/foundation_beta_readiness.v1.toml`
and documented in `docs/architecture/packaging_model.md`.

## 0.1.0-alpha.3 authored assets

The private manual-test draft contains exactly:

```text
FacMan-0.1.0-alpha.3-windows-x64-portable.zip
FacMan-0.1.0-alpha.3-windows-x64-setup.exe
FacMan-0.1.0-alpha.3-macos-x64-portable.zip
FacMan-0.1.0-alpha.3-macos-x64-setup.pkg
FacMan-0.1.0-alpha.3-linux-x64-portable.tar.zst
FacMan-0.1.0-alpha.3-linux-x64-setup.run
FacMan-0.1.0-alpha.3-SHA256SUMS.txt
FacMan-0.1.0-alpha.3-evidence.zip
```

There are no separately authored JSON, SBOM, provenance, licence, CLI, TUI,
or toolkit-specific release assets. Those records live inside the product
packages or the consolidated evidence archive as appropriate.

## Claims

| Platform | Architecture | GUI | Terminal/TUI | Status |
| --- | --- | --- | --- | --- |
| Windows 10 22H2 / 11 | x64 | WinForms implementation, public name `FacMan` | `facman`, `facman tui` | private alpha manual test; 0.1 support direction |
| macOS 13+ | Intel x64 | AppKit implementation, public name `FacMan` | `facman`, `facman tui` | experimental private preview |
| Ubuntu 24.04 reference | x64 | GTK 3/X11 implementation, public name `FacMan` | `facman`, `facman tui` | experimental private preview |

Apple Silicon, universal2, Linux ARM, Wayland/Qt, signing, notarization,
automatic update, public support, and real-Factorio execution are absent.

## Historical and future lanes

Older CLI-only, TUI-preview, and toolkit-specific profiles remain internal
qualification inputs. Alpha.2 remains immutable and is superseded only because
its public distribution shape did not meet the unified product contract.

Later beta/RC/final releases may add architectures, signing, notarization,
native maintenance improvements, or additional supported Linux profiles only
through separately admitted release work. They must not silently change the
alpha.3 claim.

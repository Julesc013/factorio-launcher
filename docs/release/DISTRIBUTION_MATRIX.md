# Distribution Matrix

The version-current 0.1 distribution is selected only by
`release/index/active_release_view.v1.toml`: three whole-product profiles and
eight authored assets. `release/index/foundation_beta_readiness.v1.toml`
records readiness, while `docs/architecture/packaging_model.md` defines the
construction model.

## Current eight-asset shape

Substitute the exact selected version for `<version>`:

```text
FacMan-<version>-windows-x64-portable.zip
FacMan-<version>-windows-x64-setup.exe
FacMan-<version>-macos-x64-portable.zip
FacMan-<version>-macos-x64-setup.pkg
FacMan-<version>-linux-x64-portable.tar.zst
FacMan-<version>-linux-x64-setup.run
FacMan-<version>-SHA256SUMS.txt
FacMan-<version>-evidence.zip
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
qualification inputs and are not current downloads. The immutable Alpha.3
distribution remains in `release/index/final_distribution.v1.toml` as a
historical draft whose successor is the final Alpha.5 candidate receipt.

Later beta/RC/final releases may add architectures, signing, notarization,
native maintenance improvements, or additional supported Linux profiles only
through separately admitted release work. They must not silently change the
current selector.

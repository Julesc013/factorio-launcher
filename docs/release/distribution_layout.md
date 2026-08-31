# Distribution Layout

The primary FacMan distribution is a platform product, not a set of frontend
fragments. Each portable package and its matching setup package expose the
same two public surfaces:

```text
FacMan       native graphical application
facman       terminal application: JSON, human CLI, and facman tui
```

There is no separate `facman-tui`, CLI download, TUI download, WinForms
download, AppKit download, or GTK download.

## Alpha.3 layouts

| Platform | GUI | Terminal | Portable container | Setup container |
| --- | --- | --- | --- | --- |
| Windows x64 | `FacMan.exe` | `bin/facman.exe` | ZIP | self-contained EXE |
| macOS Intel x64 | `FacMan.app` / `Contents/MacOS/FacMan` | `FacMan.app/Contents/MacOS/facman` | ZIP | PKG |
| Linux x64 | `FacMan` | `facman` | tar.zst | self-contained RUN |

The Windows subdirectory is required by the platform's case-insensitive path
rules. It does not create a separate product or download.

Every layout also contains the exact shared runtime libraries, contracts,
Factorio content, licences, release records, and hash-closed manifests required
by its profile. GUI toolkit names are allowed in internal component records but
not in public asset or entrypoint names.

Portable archives perform no installation and must be extracted into a new
empty directory for testing. Setup packages perform the documented installation
effects and must work without downloading another payload.

## Contract checks

`release/profiles/*_product_x64/profile.toml` declares entrypoints and required
components. `release/packaging/*/platform_product.v1.toml` declares their
package destinations. The layout, skeleton, manifest, producer, artifact-name,
and final-distribution validators cross-check those sources.

Historical package profiles remain available for regression evidence only.
They do not enlarge the authored alpha.3 asset set.

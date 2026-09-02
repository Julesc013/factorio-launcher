# Packaging Model

FacMan ships one user-facing product package per platform. It does not ship
separate CLI, TUI, or toolkit-branded primary downloads.

Every current 0.1 platform stage contains:

- a native GUI whose public name is `FacMan`;
- one terminal host named `facman` for machine JSON, human CLI, and
  `facman tui`;
- the required launcher/setup-provider and Factorio-binding runtime closure for
  that profile;
- one verified `facman.resources` archive containing the selected runtime
  contracts and Factorio content;
- licences and package metadata.

The components remain replaceable internally. WinForms, AppKit, and GTK are
implementation details and must not appear in primary asset names.

The exact alpha.5 package candidate passed as an internal, unsigned,
unpublished machine qualification in run `33603385303`, attempt 1, from source
revision `4683ecd9a1b9ead5eb84be152760d12583da0f0e` and tree
`c07938618bc0f533fd12756cba123f54b8592048`. The reference Windows shell is
WinForms on .NET Framework 4.8. GTK3 on Ubuntu 24.04 x64/X11 and AppKit on
macOS 13+ Intel are machine-qualified semantic previews. Human install,
accessibility, performance, support, signing, notarization, and publication
remain separate gates.

## Windows x64

```text
FacMan-<version>-windows-x64-portable.zip
  FacMan.exe
  bin/
    facman.exe
    ulk.dll
    usk.dll
    flb_factorio.dll
  facman.resources
  docs/
  licenses/
  manifest/
  release/
```

Windows treats file names that differ only by case as identical, so
`FacMan.exe` and `facman.exe` cannot safely occupy the same directory. The GUI
therefore lives at the package root and the terminal host lives under `bin/`.
They are still delivered as one product download.

The matching setup candidate is one self-contained offline executable:

```text
FacMan-<version>-windows-x64-setup.exe
```

It embeds the complete portable payload. There is no payload sidecar.

## macOS Intel x64

```text
FacMan-<version>-macos-x64-portable.zip
  FacMan.app/
    Contents/MacOS/
      FacMan
    Contents/Helpers/
      facman
    Contents/Resources/
      facman.resources
      docs/
      licenses/
      manifest/
      release/
```

The Intel terminal closure is statically linked for this experimental package;
no provider dylibs are claimed.

The matching setup candidate is
`FacMan-<version>-macos-x64-setup.pkg`. Its declared payload targets the app
under `/Applications` and exposes the embedded terminal host as
`/usr/local/bin/facman`. Current candidates are unsigned, not notarized, and
have no human installation verdict.

## Linux x64

```text
FacMan-<version>-linux-x64-portable.tar.zst
  FacMan-<version>/
    FacMan
    facman
    lib/
    share/facman/
```

The preview GUI is GTK 3/X11, but the executable and asset names remain
`FacMan`. The matching self-contained offline setup candidate is
`FacMan-<version>-linux-x64-setup.run`; it defaults to current-user paths under
`~/.local` and implements install, verify, repair, and uninstall. Human
installation and wider Linux/Wayland claims remain unproven.

## Release and manifest truth

The current public release law is exactly eight authored assets: six product
packages (portable and setup for Windows x64, macOS Intel x64, and Linux x64),
one versioned checksum list, and one consolidated evidence archive. The latter
two are companions, not separate products. The governing current sources are:

- `release/index/foundation_beta_readiness.v1.toml`;
- `release/index/version.v2.toml`;
- `release/index/artifact_matrix.v1.toml`;
- `release/index/package_producers.v1.toml`;
- `release/profiles/{windows,macos,linux}_product_x64/profile.toml`;
- `release/packaging/{windows,macos,linux}/platform_product.v1.toml`.

`tools/package_layout_check.py`, `tools/package_manifest_check.py`, and
`tools/package_skeleton_check.py` validate the declared package closure.
`tools/package_contract_tck.py` validates stage shape and setup-payload
equivalence. `.github/workflows/product-candidate.yml` built and verified the
six exact unsigned alpha.5 products without tagging or publishing them. Its
four workflow artifacts culminated in a 14-file internal bundle: six products,
six platform/equivalence records, `SHA256SUMS`, and a candidate manifest. That
bundle is evidence transport, not the final eight-asset public release factory.
Exact-byte human and authority receipts remain separate gates.

The binding receipt is
`release/index/alpha5_promotion_candidate_closeout.v1.toml`. It qualifies only
the recorded source revision and tree; the closeout revision and every future
revision require a fresh candidate run.

Historical CLI-only, TUI-preview, and toolkit-specific profiles remain
internal compatibility and qualification lanes. They are not current primary
downloads. The immutable alpha.3 inventory remains historical truth in
`release/index/alpha3_release_source.v1.toml` and
`release/index/final_distribution.v1.toml`.

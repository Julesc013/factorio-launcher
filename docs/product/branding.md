# Branding

Public product language must make unofficial status obvious.

Approved wording:

```text
FacMan - an unofficial launcher and isolated instance manager for Factorio
Factory Launcher for Factorio
```

Avoid official Factorio or Wube logos, trade dress, and wording that implies
endorsement.

FacMan's OEM+ identity may brand the application icon, product accent, page
headers, selected-instance artwork, Launch Deck, status symbols, empty states,
modpack artwork, update illustrations, and About surface. It must not imitate
Factorio or Wube trade dress.

Window chrome, menus, dialogs, text entry, scrolling, focus, selection, button
ordering, keyboard behavior, system fonts, and familiar system-command icons
remain platform-native. Branding the product does not authorize replacing the
operating system's interaction language. The complete appearance contract is
`docs/product/interface_design_system.md`.

## Provisional application identity

The operator-supplied orange gear artwork is admitted only as a provisional
FacMan application mark for internal candidate construction. Its tracked source,
candidate hashes, deterministic platform derivatives, and review boundaries are
recorded in
`content/factorio/ui/branding/provenance/branding-asset-manifest.v1.json`. The
generated contact sheet is `content/factorio/ui/branding/review/contact-sheet.png`.

`tools/generate_branding_assets.ps1` produces the Windows ICO, macOS ICNS, and
Linux hicolor PNG set from the exact reviewed source digest. Run
`python tools/branding_asset_check.py` to verify every output byte, container
entry, dimension, platform package hook, and authority exclusion.

This technical admission does not establish official Factorio/Wube status,
approve public trademark use, authorize production signing, or activate a
public release/support route. Small-size optical correction, public brand and
trademark judgment, and experiential High Contrast/DPI review remain human.

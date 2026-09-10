# Active release view

`release/index/active_release_view.v1.toml` is the sole selector for current
FacMan release obligations. The wider profile, support, distribution, update,
and producer files remain exhaustive catalogs; catalog membership alone never
makes a profile, lane, producer, candidate, or asset current.

## Selected 0.1 product

| Role | Profile | Public package obligation |
| --- | --- | --- |
| Reference | `windows_product_x64` | portable ZIP and setup EXE |
| Selected preview | `macos_product_x64` | portable ZIP and setup pkg |
| Selected preview | `linux_product_x64` | portable tar.zst and setup run |

Every selected package contains one platform-native `FacMan` GUI and the same
`facman` terminal host for machine JSON, human CLI, and `facman tui`.
Windows is the 0.1 reference direction. macOS Intel/AppKit and Linux
GTK3/X11 are explicitly selected previews whose semantic and human gates remain
open.

The public release shape is exactly eight assets: those six product packages,
one checksum file, and one consolidated evidence archive. The Alpha.5 candidate
receipt proves an internal 14-file evidence bundle; it does not change the
eight-asset public shape.

## Catalog and history boundary

The compatibility CLI/TUI profiles, toolkit-specific profiles, and their
distribution lanes remain inspectable for construction, regression, and
historical evidence. They all declare
`current_release_obligation = false`. The package manifest and release index
retain their complete profile-path arrays for backward-compatible construction,
but label those arrays as catalogs and publish separate active selections.

The earlier Alpha.5 candidate receipt is
`historical_alpha5_candidate`; the Alpha.3 distribution is
`historical_alpha3_draft`. Both point to the final Alpha.5 candidate receipt
as their current successor and neither may be selected by a current view.

Only `platform_product_bundle` and `platform_self_setup` are current
producers. Legacy exceptions remain historical compatibility producers.
Provider SDK, maintenance, and additional native-adapter producers remain
future and unadmitted.

## Validation and authority

`tools/active_release_view_check.py` fails closed across the selector, JSON
schemas, release index, package manifest, support matrix, distribution lanes,
producer census, update report, profile catalog, artifact matrix, and
historical receipts. It is part of strict validation and the hosted schema
workflow.

The view records selection, not approval. It grants no human acceptance,
release, signing, tagging, publication, or support authority. Product changes
require a reviewed update to the selector and every cross-validated catalog;
editing a catalog row alone cannot enlarge the release.

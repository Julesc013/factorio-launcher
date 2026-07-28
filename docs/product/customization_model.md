# Customization Model

FacMan customization is tiered so user control does not become arbitrary code
execution.

## C0 User Preferences

Examples:

- appearance mode: System Native, OEM+, or an accepted Custom theme
- theme package
- font size
- density
- default workspace
- default instance template
- default launch profile
- preferred frontend

These belong in workspace preferences, not in package manifests.

System Native is always available and is the compatibility, accessibility, and
recovery baseline. OEM+ may brand bounded product surfaces while retaining
native controls and platform behavior. Custom themes are optional and may not
override accessibility enforcement, focus, semantic status, warning,
confirmation, or safe-mode behavior.

## C1 Declarative Product Content

Examples:

- instance templates
- launch templates
- diagnostic bundle templates
- export templates
- compatibility rules
- discovery hints
- redaction rules
- server templates

Package defaults live under `content/factorio/`. User templates live under the
workspace and must remain declarative.

## C2 Declarative Workflows

Workflows are ordered command-graph steps with declared inputs and effects.
They must call existing commands instead of inventing GUI-only behavior.

## C3 Signed Declarative Recipes

Signed recipes describe diagnosis, compatibility correction, installation
repair, and host repair using versioned allowlisted typed actions. They never
contain arbitrary shell strings, cannot introduce effects outside their signed
declaration, cannot issue operation permits, and cannot access raw credentials.
Expiry, revocation, anti-rollback, target predicates, verification, and honest
rollback or recovery classes are mandatory before recipe apply is enabled.

## C4 External Extensions — deferred

Out-of-process or WASI-style providers may eventually support a demonstrated
third-party source, content repository, analysis, or mod-development need.
They are post-v1 options, not a current framework project. They must declare
capabilities and can never receive direct setup mutation, process execution,
arbitrary filesystem, permit-issuance, or credential-value authority.

Dynamic in-process native plugins are not an accepted extension model.

Themes are a separate data-only trust class. A theme may provide allowlisted
semantic tokens, icons, artwork, licenses, bounded density preferences, and
bounded platform token overrides. It may not contain executable code, scripts,
QML, XAML, raw GTK CSS, unrestricted Qt style sheets, remote URLs, commands,
dynamic libraries, arbitrary layouts, or unbounded vector features.

Theme loading must validate manifests, hashes, paths, formats, dimensions,
decoding cost, and total size in a staging representation. Failure falls back
to System Native and must never create a startup crash loop. A startup bypass
must disable all custom themes.

Presentation contributions, provider connectors, game-content mods, and
first-party static modules are not themes. Each has a separate trust and
capability model described in `docs/product/interface_design_system.md`.

Current theme and string resources live in:

- `content/factorio/strings/en-US.toml`
- `content/factorio/ui/themes/default.toml`
- `content/factorio/ui/themes/high_contrast.toml`

The existing `facman.ui.theme.v1` resources predate the full appearance model.
They remain current implementation inputs until `THEME-V1-01` defines the
bounded package, native-token mapping, migration, and safe-mode contract. Their
existence does not make arbitrary application-wide styling a supported claim.

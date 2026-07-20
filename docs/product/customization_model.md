# Customization Model

FacMan customization is tiered so user control does not become arbitrary code
execution.

## C0 User Preferences

Examples:

- theme
- font size
- density
- default workspace
- default instance template
- default launch profile
- preferred frontend

These belong in workspace preferences, not in package manifests.

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

UI themes and strings currently live in:

- `content/factorio/strings/en-US.toml`
- `content/factorio/ui/themes/default.toml`
- `content/factorio/ui/themes/high_contrast.toml`

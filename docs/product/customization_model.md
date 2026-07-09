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

## C1 Declarative Templates

Examples:

- instance templates
- launch templates
- diagnostic bundle templates
- export templates

Package defaults live under `content/factorio/`. User templates live under the
workspace and must remain declarative.

## C2 Declarative Workflows

Workflows are ordered command-graph steps with declared inputs and effects.
They must call existing commands instead of inventing GUI-only behavior.

## C3 Sandboxed Extensions

Extensions are deferred until schemas, package contracts, credential policy,
and command effects are stable. Future extension manifests must declare
capabilities and must not receive direct credential access or install mutation
authority by default.

UI themes and strings currently live in:

- `content/factorio/strings/en-US.toml`
- `content/factorio/ui/themes/default.toml`
- `content/factorio/ui/themes/high_contrast.toml`

# Modsets

Owns Factorio modset semantics.

May contain:

- modset lockfile generation and verification
- dependency and incompatibility interpretation
- local mod ZIP import/export helpers
- Mod Portal release-to-lockfile projection

Must not contain:

- universal launcher artifact-set policy
- generic package dependency resolution
- GUI-only mod behavior

Universal Launcher may model artifact sets generically. Factorio-specific
modset law stays here.

## Current Local ZIP Semantics

- `mods import <zip>` copies only local `.zip` files into an isolated instance.
- If the archive is a safe stored ZIP and contains `info.json` at the root or
  under a top-level mod directory, FacMan reads `name`, `title`, `version`,
  `factorio_version`, and string `dependencies`.
- Dependencies starting with `?` are recorded as optional dependencies.
- Dependencies starting with `!` are recorded as incompatibilities.
- Archives without readable metadata still import, but their mod identity falls
  back to the `<name>_<version>.zip` filename convention.
- No network Mod Portal lookup or token behavior is involved in local ZIP
  import.

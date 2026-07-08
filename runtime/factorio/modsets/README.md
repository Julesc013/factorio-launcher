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

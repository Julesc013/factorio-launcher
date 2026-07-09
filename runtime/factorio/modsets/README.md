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
- Import validates the ZIP before copying; invalid metadata returns a
  structured refusal and does not partially install.
- Safe stored ZIPs with readable `info.json` produce structured mod refs with
  SHA-1, SHA-256, required dependencies, optional dependencies,
  hidden-optional dependencies, and incompatibilities.
- Lock/export refuses duplicate versions, unsatisfied required dependencies,
  incompatible pairs, Factorio-version mismatches, and invalid ZIPs.
- Verify recomputes SHA-1 and SHA-256 from local artifacts and reports
  `mod_hash_mismatch` when an artifact drifts.
- No network Mod Portal lookup or token behavior is involved in local ZIP
  import.

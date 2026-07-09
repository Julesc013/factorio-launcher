# Mods

Owns local Factorio mod ZIP interpretation.

Current local semantics:

- Accept local `.zip` files only.
- Require the filename shape `<name>_<version>.zip`.
- Require readable `info.json` at the archive root or under the top-level mod
  directory.
- Parse `name`, `title`, `version`, `factorio_version`, `author`,
  `description`, and string dependencies.
- Parse required dependencies, `?` optional dependencies, `~` hidden-optional
  or load-order dependencies, and `!` incompatibilities.
- Compute SHA-1 and SHA-256 over the exact local ZIP.
- Return structured refusals instead of falling back to guessed metadata for
  unsafe or unsupported inputs.

This folder must not contact the Mod Portal, read account credentials, mutate
global Factorio mod directories, or perform setup-owned install mutation.

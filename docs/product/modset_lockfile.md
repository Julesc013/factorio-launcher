# Modset Lockfile

Modsets are reproducibility records. A lockfile pins the Factorio version, mod
names, versions, hashes, source, dependency declarations, and cache references.

The Mod Portal adapter is Factorio-specific because its public shape is not a
universal launcher contract.

## Implemented Native Slice

FacMan-MODSET-01 is local-only:

```bash
facman mods import ./example_1.2.3.zip --instance <id> [--json]
facman modsets lock <id> [--json]
facman modsets verify <id> [--json]
facman modsets export <id> ./pack.zip [--json]
```

`mods import` copies a local ZIP into the instance `mods/` directory and derives
the initial mod name/version from the `<name>_<version>.zip` filename.
`modsets lock` writes `mods/modset-lock.v1.json` under the instance and mirrors
the lockfile to `modsets/<instance>.modset-lock.v1.json` in the workspace.
`modsets verify` recomputes local SHA-1 values and reports mismatches.
`modsets export` writes a stored ZIP pack containing the lockfile and local mod
ZIPs.

This slice does not call the Mod Portal, resolve dependencies, download mods,
or mutate global Factorio mod directories.

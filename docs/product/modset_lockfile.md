# Modset Lockfile

Modsets are reproducibility records. A lockfile pins the Factorio version, mod
names, versions, hashes, source, dependency declarations, and cache references.

The Mod Portal adapter is Factorio-specific because its public shape is not a
universal launcher contract.

## Implemented Native Slice

FacMan-MODSET-01 and FACMAN-MODZIP-DEPTH-02 are local-only:

```bash
facman mods import ./example_1.2.3.zip --instance <id> [--json]
facman modsets lock <id> [--json]
facman modsets verify <id> [--json]
facman modsets export <id> ./pack.zip [--json]
```

`mods import` validates a local ZIP before copying it into the instance
`mods/` directory. The filename must be `<name>_<version>.zip`, and `info.json`
must agree with that name and version.

The local parser reads:

- `name`
- `title`
- `version`
- `factorio_version`
- `author`
- `description`
- required dependencies
- optional dependencies using `?`
- hidden-optional or load-order style dependencies using `~`
- incompatibilities using `!`

`modsets lock` writes `mods/modset-lock.v1.json` under the instance and mirrors
the lockfile to `modsets/<instance>.modset-lock.v1.json` in the workspace.
Lock entries include SHA-1 and SHA-256 hashes, source, enabled state, structured
dependencies, structured optional dependencies, and structured
incompatibilities.

`modsets verify` recomputes local SHA-1 and SHA-256 values and reports
mismatches with a structured `mod_hash_mismatch` refusal.
`modsets export` writes a stored ZIP pack containing the lockfile and local mod
ZIPs. The export contains the lock and local mod artifacts, not credentials or
absolute machine-local paths.

Local modset lock/export refuses:

- missing or malformed `info.json`
- invalid filenames
- filename/info name mismatch
- filename/info version mismatch
- unsupported dependency syntax
- unsatisfied required dependencies
- incompatible pairs
- duplicate versions of the same mod
- Factorio-version mismatches

This slice does not call the Mod Portal, resolve dependencies, download mods,
or mutate global Factorio mod directories.

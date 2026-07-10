# Install Discovery

The first discovery implementation is read-only.

Commands:

```bash
facman installs scan [--path <root>] [--search-root <root>] [--json]
facman doctor [--search-root <root>] [--json]
facman installs list
facman installs inspect <install-id> [--json]
facman installs import <path> --id <install-id> [--json]
```

Ownership classifications:

- `managed`: universal setup owns mutation
- `foreign`: Steam, installer, or package manager owns it
- `imported`: user selected folder, mutation disabled
- `portable`: user-controlled portable tree

No repair or uninstall is allowed for foreign-owned installs.

## Implemented Native Slice

`installs scan` is read-only. It inspects explicit `--path` roots, optional
`--search-root` roots, optional `;`-separated `FACMAN_DISCOVERY_ROOTS`, and
conservative platform defaults. It reports candidate install refs but does not
register them. Registration remains an explicit `installs import` action.

`doctor --search-root <root> --json` embeds the same read-only discovery report
for explicit roots. Without explicit roots, doctor remains host-independent and
does not scan the machine.

The native scanner recognizes:

- manually selected standalone folders
- Steam library layouts under `steamapps/common/Factorio`
- portable folders
- headless folders
- macOS `.app` bundles
- invalid folders, reported with `verification.status = invalid`
- fixture manifests under `tests/fixtures/factorio_installs/`, used only for
  deterministic tests and not as host metadata

All discovered refs report `safe_actions.repair = false` and
`safe_actions.uninstall = false`.

## Fixture Proof

`FACMAN-DISCOVERY-FIXTURES-02` adds deterministic fixtures and goldens for:

- Windows Steam
- Windows standalone
- Windows portable
- macOS app bundle
- macOS invalid bundle
- Linux tarball
- Linux headless
- Linux OS-package-owned
- imported/adoptable
- invalid

## Windows Read-Only Providers

`FACMAN-WINDOWS-DISCOVERY-01` adds real read-only Windows providers without
registration or setup authority:

- Steam roots from conservative defaults and Valve's user/machine registry
  values.
- Steam libraries from bounded `steamapps/libraryfolders.vdf` parsing,
  including current `path` records and the legacy numeric-key form.
- Default and explicitly injected standalone installation roots.
- Stable, case-insensitive path de-duplication and deterministic output order.
- Refusal to cross a symlink, junction, or reparse point in any discovered
  candidate path.

`FACMAN_STEAM_ROOTS` and `FACMAN_STANDALONE_ROOTS` are semicolon-separated
provider overrides used for deterministic tests and unusual local layouts.
`FACMAN_DISCOVERY_DISABLE_DEFAULTS=1` disables registry and standard-path
probing while retaining explicit provider overrides. These are discovery
inputs only; they never authorize writes.

The provider proof covers malformed VDF metadata, duplicate libraries,
Unicode and long paths, missing executables, foreign ownership, zero workspace
writes, stable ordering, and junction refusal. It does not yet parse macOS
Spotlight records or Linux package-manager databases.

# Discovery

Factorio install discovery and ownership classification.

Current implementation:

- `discovery_service.*` owns bounded provider composition and path-list policy;
  `provider_explicit.*`, `provider_windows.*`, `provider_linux.*`, and
  `provider_macos.*` enumerate platform roots; `steam_vdf.*` performs stable
  no-follow Steam metadata reads; `flb_factorio_discovery.*` inspects and
  renders candidates.
- `apps/cli/` parses command arguments such as `--path`, delegates discovery
  here, and writes imported install refs only after the operator chooses
  `installs import`.
- Scan remains read-only: no install, repair, uninstall, Steam mutation,
  download, or default Factorio data-directory write occurs during discovery.
- An explicit version-library root also yields structural direct children, so
  numeric directories such as `1.1`, `2.0`, and `2.1` do not depend on a name
  containing `factorio` and do not produce an invalid parent false positive.
- Windows providers inspect Steam registry roots, parse bounded
  `libraryfolders.vdf` metadata, and inspect standalone/default roots. Results
  are deterministically de-duplicated.
- Windows provider tests cover spaces, Unicode and long paths, malformed
  metadata, read-only behavior, and junction refusal.
- Linux providers cover explicit roots, `FACMAN_DISCOVERY_ROOTS` using `:`,
  Steam and Flatpak Steam data roots, `~/factorio`, `/opt/factorio`, standalone,
  tarball, and headless layouts without package-manager execution.
- macOS providers cover explicit roots, user/system `Factorio.app` bundles and
  Steam `libraryfolders.vdf` without Spotlight or recursive home scans.
- Every candidate records its provider id, source, ownership, root, executable,
  version, platform, capabilities, verification status, diagnostic code, and
  evidence, plus program layout, data routing, program/data separation,
  uninstaller presence, side-by-side registration risk, and local player-data
  domains. Directory entries, roots, candidates, metadata bytes, depth, and
  elapsed time are bounded. Lifecycle policy is documented in
  `docs/architecture/multi_version_install_lifecycle.md`.

Windows read-only discovery is implemented. Linux and macOS read-only
providers are also implemented. Spotlight and
Linux package-manager databases remain unnecessary optional work; discovery
does not invoke them.

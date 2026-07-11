# Discovery

Factorio install discovery and ownership classification.

Current implementation:

- `flb_factorio_discovery.*` owns read-only install inspection, source-family
  inference, ownership classification, structural verification, default search
  roots, fixture-safe scan expansion, and install-ref JSON output.
- `apps/cli/` parses command arguments such as `--path`, delegates discovery
  here, and writes imported install refs only after the operator chooses
  `installs import`.
- Scan remains read-only: no install, repair, uninstall, Steam mutation,
  download, or default Factorio data-directory write occurs during discovery.
- Windows providers inspect Steam registry roots, parse bounded
  `libraryfolders.vdf` metadata, and inspect standalone/default roots. Results
  are deterministically de-duplicated.
- Windows provider tests cover spaces, Unicode and long paths, malformed
  metadata, read-only behavior, and junction refusal.

Windows read-only discovery is implemented. The deferred provider work is
macOS Spotlight and Linux package-manager databases, not another Windows pass.

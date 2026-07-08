# Ownership Model

Repositories are product boundaries. Directories are ownership boundaries.
Files are module boundaries. Functions are ABI boundaries. Commands are
frontend boundaries. Schemas are compatibility boundaries.

Universal setup owns install mutation:

- install
- verify
- repair
- uninstall
- stage, commit, rollback
- installed-state manifests
- setup audit

Universal launcher owns orchestration:

- products
- install references
- instances
- profiles
- accounts
- launch plans
- command graph
- dry-run, audit, diagnostics

The Factorio binding owns Factorio-specific behavior:

- Factorio discovery
- Factorio install/version validation
- Factorio launch templates
- mods and modsets
- saves
- servers
- Mod Portal rules
- account redaction and token references

Frontends own presentation only.

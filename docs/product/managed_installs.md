# Managed Installs

FacMan does not repair or uninstall Factorio installs directly.

Managed install operations are routed through Universal Setup:

- `facman installs install-version <version> --archive <path>`
- `facman installs verify <install-id>`
- `facman installs repair <install-id>`
- `facman installs uninstall <install-id>`

The current slice is setup-backed and dry-run-oriented. It can produce setup
plans and reports, but it does not extract archives, mutate registries, call
package managers, download binaries, repair Steam installs, or uninstall
foreign-owned/imported installs.

Ownership gates:

- `managed` or `adopted`: may be planned through setup.
- `foreign_owned`, `imported`, or `portable`: repair and uninstall are refused.

This keeps the permanent boundary intact: Universal Setup mutates installed
software state; FacMan interprets Factorio-specific facts and presents setup
decisions.

The app installation mode is separate from the Factorio install origin. FacMan
itself may run from a portable, user-installed, or system-installed package, but
Factorio repair/uninstall authority still depends on whether Universal Setup
owns the specific Factorio install. See
[install_distribution_modes.md](install_distribution_modes.md).

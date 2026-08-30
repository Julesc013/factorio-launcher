# FACMAN-SELF-SETUP-AND-MAINTENANCE-PACKAGE-01

Status: implementation candidate pending protected-branch qualification and exact alpha.2 asset binding.

The implementation is a thin FacMan command shell over the exact Universal Setup revision pinned by `providers.lock.v2.toml`. FacMan owns UX, product layout, and package identity; Universal Setup remains the only mutation engine.

The lifecycle fixture proves read-only planning, verified install, owned-file damage detection,
repair, verification after repair, foreign-content uninstall refusal, clean uninstall, workspace
preservation, and retained transaction state. A second integration pass used the frozen alpha.1
WinForms portable ZIP as a realistic payload fixture without altering the alpha.1 tag, draft, or
assets.

The release candidate must still be rebuilt from the exact merged alpha.2 source, compared across
fresh independent roots, tagged forward-only, uploaded to a new private draft prerelease,
downloaded back, and hash-verified before this checkpoint is closed.

No Factorio execution, network acquisition, elevation, signing, public publication, shortcut/registry mutation, or automatic update authority is introduced.

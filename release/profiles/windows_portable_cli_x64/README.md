# Windows Portable CLI x64

First target-specific built-package proof. It contains one statically linked
`facman.exe` frontend plus required contracts, Factorio content, release
metadata, documentation, and licenses. It deliberately excludes TUI, daemon,
GUI, and unused shared-library payloads.

`facman package verify --json` checks required resources, manifest closure,
and SHA-256 consistency after extraction. The package remains local, unsigned,
and unpublished; hash consistency does not establish publisher authenticity.

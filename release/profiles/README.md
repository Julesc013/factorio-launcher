# Release Profiles

Owns named release/build profiles.

Profiles should be target-specific rather than vague. Prefer names like
`windows_legacy_winforms`, `macos_legacy_appkit`, and `linux_x11_gtk` over
generic `legacy` or `modern`.

The first contract-backed package lanes are:

- `windows_portable_cli_x64` (the first target-specific static built proof)
- `linux_portable_cli_x64` (target-specific project-static/system-dynamic CLI proof)
- `windows_legacy_winforms_x64`
- `macos_legacy_appkit_x64`
- `linux_x11_gtk_x64`
- `portable_cli_x64`
- `portable_tui_x64`
- `windows_portable_tui_x64`
- `linux_portable_tui_x64`
- `macos_portable_tui_x64`

The full release-profile catalog lives in `profile_catalog.v1.toml`. Planned
profiles may be cataloged before they become contract-backed package profiles;
only contract-backed profiles appear in `release/index/release_index.v1.toml`.

## Release Readiness Ladder

```text
R0 - Architecture baseline
R1 - Developer preview
R2 - Local power-user alpha
R3 - Portable package and safety hardening
R4 - Managed install alpha
R5 - Native GUI preview
R6 - v1.0
```

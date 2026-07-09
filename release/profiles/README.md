# Release Profiles

Owns named release/build profiles.

Profiles should be target-specific rather than vague. Prefer names like
`windows_legacy_winforms`, `macos_legacy_appkit`, and `linux_x11_gtk` over
generic `legacy` or `modern`.

## Release Readiness Ladder

```text
R0 - Architecture baseline
R1 - Developer preview
R2 - Local power-user alpha
R3 - Safe beta
R4 - Managed install alpha
R5 - Native GUI preview
R6 - v1.0
```

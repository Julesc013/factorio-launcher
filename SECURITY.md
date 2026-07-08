# Security Policy

FLaunch manages paths, launch arguments, logs, mod archives, save files, and
account references. Those are user-trust surfaces.

## Mandatory Rules

- Do not store plaintext passwords.
- Do not write account tokens into manifests, logs, diagnostics, or exports.
- Do not repair, uninstall, or mutate foreign-owned installs.
- Do not silently write to Steam-owned or default Factorio data directories.
- Do not bundle Factorio binaries or redistribute paid content.
- Every destructive action must support dry-run before implementation.

## Reporting

Open a private security advisory on GitHub or contact the maintainer directly.
Include reproduction steps, affected versions, and whether secrets or user data
could be exposed.


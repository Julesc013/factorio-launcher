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

Do not open a public issue for an undisclosed vulnerability. Open a private
GitHub security advisory for `Julesc013/factorio-launcher`; if that channel is
unavailable, contact the maintainer privately through the address published on
the maintainer's GitHub profile. Never include real credentials, paid Factorio
content, or third-party personal data in a report.

Include affected version/commit, platform, reproduction steps, expected and
actual behavior, impact, and whether credentials or user data may be exposed.
Encrypted attachments may be requested after initial contact.

## Response process

- Receipt should be acknowledged within 7 calendar days.
- Triage targets 14 calendar days, but no remediation deadline is promised.
- Coordinated disclosure timing is agreed with the reporter after impact and a
  fix path are understood.
- Security fixes still require regression and release proof; a green test alone
  is not publication authorization.

## Supported versions

FacMan has no stable release. Only the current default branch and an explicitly
named package-preview candidate receive security triage. Historical R2/R3
checkpoints and unsigned proof artifacts are evidence, not supported releases.
See `docs/release/SUPPORT_POLICY.md` for platform and version scope.

## Evidence boundaries

The `security-policy` workflow validates repository policy and must not be
described as source-code vulnerability analysis. The separate `code-security`
workflow runs CodeQL v4 for the built C/C++ graph, Python, and the WinForms C#
client. Sanitizers, fuzzing, compiler hardening inspection, dependency/license
review, and secret-scanning settings remain separate evidence with separate
availability and results. A configured workflow is not a green analysis result
until GitHub Actions executes it for the exact revision.

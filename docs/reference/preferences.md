# Preferences

`facman.preferences.v1` is an optional, non-secret user configuration document.
It lives under the platform configuration directory in
`facman/preferences.v1.json`; an existing legacy configuration path is read in
place and is never silently migrated.

Supported settings cover the preferred workspace and transport, default
instance template and launch profile, color policy, TUI page size, bounded
command timeout, backup destination and keep-last policy, discovery provider
enablement, and explicit discovery roots.

Tokens, passwords, cookies, account credentials, arbitrary scripts, shell
commands, and setup-mutation authority are forbidden. Unknown fields and
unknown/future schema versions refuse before mutation.

Commands follow a reviewable plan/apply split:

- `preferences.inspect`, `preferences.validate`, and `preferences.plan` are
  read-only;
- `preferences.apply` writes through a transaction journal, stable no-follow
  reads, a unique backup, durable staging, and durable replacement;
- `preferences.reset.plan` is read-only;
- `preferences.reset.apply` preserves the prior document as a unique backup
  before removing the active preference file.

The `daemon` transport value remains unavailable and is rejected during
validation. Preferences never enable product execution, setup mutation,
network access, or credential storage.

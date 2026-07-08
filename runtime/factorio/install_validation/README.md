# Install Validation

Owns Factorio install validation reports and structural safety checks.

May contain:

- executable and application-directory validation
- base data/version checks
- ownership classification support
- read-only diagnostic report builders

Must not contain:

- repair, uninstall, rollback, or other setup mutation
- Steam mutation
- frontend formatting

Managed install repair belongs to `universal-setup`.

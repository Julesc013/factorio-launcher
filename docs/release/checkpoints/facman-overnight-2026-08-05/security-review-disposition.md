# Release-resolution security review disposition

## Overnight findings

The adversarial review demonstrated five fail-open behaviors:

1. forged stage authority or metadata accepted by package verification;
2. forged source or provider remotes projected as release-eligible;
3. Windows-special or nonportable archive entries accepted;
4. escaping hardlinks accepted;
5. excessive TAR expansion accepted.

All five were repaired in
`a8dbd1e272d463da1e49b4c74641fe51aab0064c` and remain regression-covered
at source-closure head
`bcc0233ccda9b7d29467d4ba5da613a2e016a36f`.

This disposition records repair of the demonstrated cases. It does not close
or replace the independent gate
`FACMAN-RELEASE-RESOLUTION-SECURITY-REVIEW-01`.

## Independent-review scope

The later independent review must include:

- canonical JSON and digest-domain separation;
- recursive, integer, file-count, byte-count and expansion budgets;
- case-folding, Unicode normalization, reserved-name and trailing-name
  collisions;
- junction, reparse-point, hardlink and time-of-check/time-of-use
  substitution;
- ZIP local-header versus central-directory disagreement;
- PAX, GNU and sparse TAR extensions;
- disk-exhaustion and interrupted atomic-stage replacement;
- source changes after observation;
- package-record, runtime-metadata and provenance substitution;
- developer-path, credential and environment leakage;
- unsupported-target behavior and authority escalation.

The independent reviewer must not be the implementer of the overnight
repairs.

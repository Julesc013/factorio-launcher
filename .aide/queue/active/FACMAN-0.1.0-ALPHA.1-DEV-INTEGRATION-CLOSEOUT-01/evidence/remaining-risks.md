# Remaining risks and gates

- The first and second exact-final-dev qualification runs remain diagnostic.
  Their script-entry/fail-fast and full-clone repairs passed exact-head and
  merge-head checks and were integrated normally; neither failed run produced
  an accepted package.
- The third exact-final-dev qualification run (`33195553232`) reached a full
  root 1 clone and Debug native build, then failed 38 of 39 because writable
  containment compared the physical workspace identity with its equivalent
  stable-drive spelling lexically. The bounded identity repair must pass
  exact-head and merge-head checks, after which qualification must restart in
  all three fresh roots from the resulting protected `dev` revision.
- The first protected closeout merge-head Windows job exposed a bounded
  transport-fixture timeout. The narrow reliability repair passed exact-head
  protected-PR checks, merged normally as `8fd8bf076aa88f74dd0a93f55a31d5eed5720d5a`,
  and all four resulting protected merge-head workflows passed before the first
  final-dev qualification attempt began.
- The three exact acceptance packages do not exist yet for the post-closeout
  protected `dev` revision. A successful three-fresh-root qualification run is
  required before freezing the human packet or considering tag eligibility.
- The exact-package human CLI, TUI, WinForms, keyboard, screen-reader, High
  Contrast, and scaling verdicts remain `Inconclusive`. These are human-only
  beta evidence and are not inferred from machine checks.
- Linux CLI/TUI results remain exploratory package-preview evidence. GTK is a
  frontend-only prototype and no Linux product-support claim is available.
- No accepted real Factorio Play route exists. Read-only version/help evidence
  cannot be promoted into gameplay evidence.
- The required active no-bypass `refs/tags/v0.1.0-alpha.*` ruleset is not
  currently observable. Tag-only progression therefore remains NO-GO.
- Public alpha additionally lacks an accepted route and publication authority;
  beta lacks completed human receipts; signing, support, route promotion, main
  promotion, and public publication remain unauthorized.
- The external plan and template identified by supplied SHA-256 values were not
  present in this workspace. Repository-owned replacements were authored and
  must not be represented as byte-identical copies of those external files.

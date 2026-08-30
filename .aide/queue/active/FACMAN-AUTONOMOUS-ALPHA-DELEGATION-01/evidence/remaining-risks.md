# Remaining risks and authority ceiling

- The policy is ineffective until independently reviewed and normally merged
  into protected `dev`; a task head cannot tag itself.
- The live repository had no tag-target ruleset at the recorded observation.
  The runtime gate refuses tag creation until an active no-bypass ruleset with
  no exclusions restricts update and deletion for
  `refs/tags/v0.1.0-alpha.*`. GitHub-setting mutation is outside this WorkUnit.
- The eligibility/candidate artifact producer and the three independent
  attestation issuers remain separate prerequisites. The manual workflow cannot
  invent those records.
- Independent protected-branch integration remains owner/reviewer controlled.
- Alpha signing, public prerelease publication, withdrawal, support activation,
  beta/RC/stable promotion, route effects, and human acceptance remain false.
- The broad `0.1` release goal remains incomplete: current product census and
  platform/human evidence gaps still require later WorkUnits and protected
  integration.

# Remaining risks

- `release/0.1` is not covered by the observed branch ruleset.
- Beta, RC, and stable tag namespaces are not protected by the observed tag
  ruleset.
- The branch ruleset advertises squash and rebase although repository-level
  settings currently disable both.
- Required status checks currently permit the ruleset creation exception;
  whether to retain it for `release/0.1` needs an operator decision.
- GitHub requires zero approving reviews. Programme law still requires exact
  evidence and an authorized independent integration decision; automation must
  not infer authority from mergeability.
- Applying the recommendation remains a separate operator-authorized settings
  action and must be re-observed before exact Beta.1 allocation.
- Alpha.6 migration/recovery, managed install, real Play, human GUI and
  accessibility acceptance, signing, notarization, publication, and support
  remain open.

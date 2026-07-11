# Universal repository license decision

- WorkUnit: `FACMAN-UNIVERSAL-LICENSE-OPERATOR-DECISION-01`
- Status: pending operator decision
- Repositories: Universal Launcher and Universal Setup
- Current SBOM/dependency value: `NOASSERTION`
- Patch prepared: no

FacMan must not assign licenses to sibling repositories. The operator must
explicitly choose a license for each repository or choose to retain no license.
Only after that decision may a separate provider-repository patch add license
text, copyright metadata, dependency-lock updates, and compatibility review.

Until then, package SBOMs retain `NOASSERTION`. This uncertainty is a release
and redistribution boundary and must not be converted into MIT merely because
FacMan itself is MIT licensed.

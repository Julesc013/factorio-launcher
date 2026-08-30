# Remaining risks

- Protected integration is pending and must use a normal merge commit.
- The published branch must first merge the actual protected `dev` produced by
  PR #189; this detached rehearsal is evidence, not a canonical merge identity.
- The combined contract-set digest must be regenerated again at the actual
  synchronized #188 head and may not be copied from this rehearsal.
- Compatibility classification remains advisory and allocates no public
  semantic version or third-party SDK support commitment.
- Route execution, permit issuance, Setup mutation, signing, tagging, and
  publication remain unauthorized.

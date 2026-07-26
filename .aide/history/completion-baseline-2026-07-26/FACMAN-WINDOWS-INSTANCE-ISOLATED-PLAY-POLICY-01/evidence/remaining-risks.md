# Windows instance-isolated policy remaining risks

- The policy is reviewed on `dev` but is not yet canonical on `main`.
- No candidate revision, executable identity, launch-plan identity, bounded
  candidate issuer, or instance-isolated result packet exists.
- The one exact Windows BAM disclosure is frozen policy, not a passed runtime
  observation.
- DirectInput remains suppressed rather than accepted. NVIDIA writes remain
  blocking. Any new or changed external effect must fail or become
  Inconclusive under the frozen taxonomy.
- No real Factorio run or human `Pass`, `Fail`, or `Inconclusive` verdict has
  occurred against this policy.
- Canonical policy-only promotion and ancestry synchronization must complete
  before candidate work starts.
- Public Play, product permit issuance, installation apply, credentials,
  networking, Steam, signing, publication, and Safe beta remain unavailable.

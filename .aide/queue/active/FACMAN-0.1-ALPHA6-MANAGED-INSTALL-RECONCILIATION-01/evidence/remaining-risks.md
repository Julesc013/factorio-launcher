# Managed repair planning slice — remaining risks and boundaries

- The command produces a read-only reconciliation plan. It does not inspect or
  trust an archive, repair files, update an install, remove an install, or make
  repair apply available.
- Archive existence, content, provenance and compatibility remain unverified;
  selected archive input therefore leaves the plan blocked pending source
  inspection.
- The fresh native build and focused behavior proof are Windows Debug evidence.
  PR checks must still qualify the committed source on their declared hosts.
- Genuine managed-install transitions, lease/generation behavior, foreign-state
  preservation, fault injection and crash recovery remain required by this
  WorkUnit.
- Packaging, signing, release publication, game execution and human experience
  evidence remain outside this slice.

The WorkUnit remains active. This evidence advances one acceptance slice and
does not establish Alpha.6, Beta.1 or stable release eligibility.

## Provider-backed managed uninstall planning slice — remaining risks

- The new route produces only a provider preview. It does not admit
  `installs.uninstall.apply`, target deletion, state mutation, transaction
  creation, retention cleanup or recovery.
- A positive plan against a current, owned USK installed-state fixture remains
  unexercised. That proof must bind a newly created managed fixture and retain
  its provider/target identities without using it to claim live acceptance.
- The FacMan retained evidence gates record admission; live apply must still
  independently revalidate current target, installed state, ownership, policy
  and provider revision. No transition lease, generation, crash recovery or
  foreign-state preservation proof is supplied here.
- The Windows Debug gateway result does not qualify Linux/macOS, packaging,
  signing, genuine game execution, human experience or release publication.

## Provider-backed managed uninstall planning — strengthened boundaries

- The current-source M1 fixture is positive native/source proof for planning
  only. It is private fixture evidence and does not qualify live uninstall,
  package delivery, release acceptance or a supported host matrix.
- `installs.uninstall.apply` remains unavailable. Before any future apply work,
  target, state, ownership, policy and provider revision must be revalidated
  under a reviewed transition/lease, with crash recovery and foreign-state
  preservation evidence.

## Provider-backed managed uninstall apply — remaining risks

- The implemented source is qualified against a private owned Windows Debug
  fixture. Hosted Windows plus physical Linux/macOS checks and packaged product
  behavior must still qualify the committed postimage.
- A failure after provider entry retains exact coordinator context and reports
  recovery required, but the generic recovery-apply route does not yet project
  a target-absent completed uninstall into the FacMan install reference. That
  automated recovery step remains required before the lifecycle is complete.
- Real managed Factorio install/uninstall evidence, transition concurrency beyond
  the install-reference compare-and-swap proof, and human review of retained
  foreign content remain open acceptance work.
- Update, repair apply, managed adoption/reconciliation and the other recorded
  installation lifecycle leaves remain open. Packaging, signing, game execution,
  human experience and release publication are outside this slice.

The WorkUnit remains active. This source slice alone does not establish Alpha.6,
Beta.1 or stable release eligibility.

## Managed uninstall apply postimage boundaries

- Generic recovery now detects and safely refuses the operation-specific
  uninstall journal without mutating it. Automated operation-specific recovery
  still must reconcile the target-absent/provider-complete case into the FacMan
  install reference before the lifecycle is complete.
- `installs/.repository.lock` serializes every supported `create` and `replace`
  writer in this repository. External direct file mutation is outside that
  writer protocol; the expected-preimage check detects a change observed before
  replacement, and lock release failures remain explicit errors requiring
  recovery rather than silent success.
- The current proof is a private Windows Debug fixture. Physical platform,
  packaged-product, genuine Factorio, hostile interruption, human experience,
  signing and publication gates remain open under their existing acceptance
  records.

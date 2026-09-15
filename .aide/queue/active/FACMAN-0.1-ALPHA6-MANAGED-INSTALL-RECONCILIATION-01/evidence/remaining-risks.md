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

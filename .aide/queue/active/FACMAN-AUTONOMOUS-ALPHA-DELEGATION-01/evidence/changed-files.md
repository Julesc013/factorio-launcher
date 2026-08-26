# Changed-file classification

This bounded WorkUnit changes only release-governance and validation surfaces:

- alpha delegation, version-train, autonomy, branch, current-state, release
  index, canonical plan, project-state, roadmap, README, and ledger truth;
- closed alpha tag eligibility and receipt schemas;
- the fail-closed tag gate, receipt writer, release workflow, schema workflow,
  strict/programme/CI validators, and positive/adversarial tests;
- release factory, handbook, repository governance, checkpoint, safety-claim,
  support-matrix, and generated command/version documentation; and
- AIDE queue lifecycle records for this WorkUnit and the externally blocked
  Factorio route WorkUnit.

The change does not touch immutable route v1/v2/index, workspace or provider
locks, provider repositories, product runtime behavior, credentials, or any
published artifact. The TUI ConPTY change is a test-harness isolation repair:
it prevents the host's `TERM=dumb`/`NO_COLOR` environment from disabling the
PTY mode the test is specifically exercising.

# Remaining Risks

- Save recognition must remain explicitly shallower than deep Factorio save
  semantics; structural ZIP validity is not sufficient for a full-validity
  claim.
- Cross-volume and interruption behavior needs deterministic stage injection
  before this WorkUnit can pass.
- The subsequent transaction-recovery WorkUnit remains responsible for one
  bounded journal shared by currently enabled multi-file writers.
- Diagnostics, `run.execute`, real Factorio isolation, Safe beta, setup
  mutation, signing, release, and publication remain outside this scope.

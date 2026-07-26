# Changed files

- `tools/instance_isolated_verdict_coordinator.py`
  - derives a closed current verification identity from the no-follow stable
    file identity, exact executable bytes, exact version and exact signer;
  - derives the installation state revision from the complete staged record;
  - emits `active` only with `verification.status = pass`;
  - refuses malformed, missing, linked, stale or mismatched input before
    creating the workspace.
- `tools/instance_isolated_candidate_qualification.py`
  - passes the authenticated product identity into staging.
- `tests/test_instance_isolated_verdict_coordinator.py`
  - proves exact evidence creates a bound active record;
  - proves a mismatched digest fails before workspace creation.
- `tests/test_instance_isolated_candidate_qualification.py`
  - verifies the producer passes its exact product identity to staging.
- AIDE queue, compact state, release state and evidence surfaces
  - record the discovered fail-closed blocker and bounded repair.

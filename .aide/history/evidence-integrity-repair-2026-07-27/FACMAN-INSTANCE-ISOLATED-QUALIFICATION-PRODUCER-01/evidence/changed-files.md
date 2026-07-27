# Changed files

The WorkUnit changes only the candidate-qualification and operator-evidence
boundary:

- `tools/instance_isolated_candidate_qualification.py` validates one exact
  remote-source-closure proof, authenticated Factorio source and four exact
  build artifacts, stages the disposable Instance once, derives its current
  identities, and emits a closed qualification binding and report.
- `tools/instance_isolated_verdict_coordinator.py` accepts a producer-created
  workspace only after its source, repository, artifact, Factorio and Instance
  facts reproduce the immutable binding.
- two closed schemas define the emitted binding and report.
- focused tests cover exact closure, binding identity, non-executing
  projection, prequalified workspace reuse, malformed blockers and stale
  inputs.
- queue and architecture documents record the new prerequisite and the
  accepted harness merge.

No product runtime, frozen policy, package capability, public command, permit
issuer, route capability or authority changes.

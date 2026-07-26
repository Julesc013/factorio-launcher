# Changed files

The implementation remains inside the approved operator/evidence boundary:

- `tools/play_verdict_route.py` owns the immutable closed route and
  qualification-binding model.
- `tools/instance_isolated_verdict_coordinator.py` stages exact qualified
  bytes, prepares fresh evidence and records non-executing operator artifacts.
- Gate 4C preflight, baseline, observer and verdict tools are route-aware while
  preserving the historical Verdict 03 defaults.
- The native verdict harness verifies and projects either exact frozen route,
  with route-specific reobservation, protected resources and automated cases.
- Python and native tests cover qualification closure, dirty-source refusal,
  completion evidence, BAM disclosure, principal identity, resource ownership
  and unknown-route refusal.
- Architecture documentation records the new boundary and human handoff.

No policy, product runtime, application, release manifest, package profile,
capability or public command changed.

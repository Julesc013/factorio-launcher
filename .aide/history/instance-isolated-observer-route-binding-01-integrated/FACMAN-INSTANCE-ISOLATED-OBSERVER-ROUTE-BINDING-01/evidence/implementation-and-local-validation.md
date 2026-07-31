# Implementation and local validation

Observed at `2026-07-31T16:59:15Z` from exact base
`59422fdfe67f80cba0c91738d3e8145d7795d92c` (`origin/dev`).

## Implemented boundary

- The observer self-test now requires the exact absolute staged
  `artifacts/qualification-binding.v4.json` path for the instance-isolated
  route.
- It no-follow audits the task root and binding, validates the closed binding
  and digest, resolves the route by exact ID, and requires the clean repository
  tooling revision to equal the bound FacMan revision.
- The emitted WorkUnit and candidate revision come from the qualification,
  while historical hermetic Verdict-03 remains an explicit no-binding mode.
- The successor schemas and producer are immutable v4 / qualification-05 /
  revalidation-04 contracts.
- The native harness accepts exactly revalidation-04 for the
  instance-isolated route and independently rejects revalidation-02,
  revalidation-03, unknown WorkUnits, and the distinct hermetic route.

## Passing local evidence

```text
focused and cross-component Python tests  134 passed, 2 unsupported symlink skips
schema validation                         306 schemas passed
strict validation                         passed
AIDE Lite validation                      passed
native verdict-harness compilation        passed
native route-binding smoke                passed (1/1)
project-state validation                  passed
canonical plan generation check           passed
git diff check                            passed
```

The two Python skips are the repository's existing Windows symlink-creation
unsupported cases. The full promotion profile was also exercised as a broad
diagnostic: 555 tests ran, but its aggregate result is not counted as passing
because this isolated worktree did not use the CI `build/native-smoke` layout
and unrelated MinGW Unicode-path journey checks failed. None of those failures
touch the changed observer, qualification, route, schema, planning, or native
route-binding surfaces. Hosted PR workflows remain required.

## Authority boundary

No WPR/ETW recording, observer evidence, execution-state lease, prepare,
baseline, permit, Factorio execution, human verdict, route promotion, Setup
mutation, credential/network use, signing, or publication occurred.

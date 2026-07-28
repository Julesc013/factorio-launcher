# Validation

Status: PASS.

This WorkUnit implements and synthetically validates evidence-only operator
tooling. It does not issue a permit, start Factorio, capture WPR evidence,
record a human verdict, accept a route or promote product authority.

Observed local results on Windows x64:

- focused route/evidence Python suite: 83 tests passed, 2 expected skips;
- complete native CTest graph: 54 of 54 passed;
- complete supported raw Python suite after the full native build: 522 tests
  passed with 9 expected skips;
- strict validation: 298 schemas and every registered structural, policy,
  package, security and cross-repository check passed;
- candidate smoke, permit smoke, installed SDK smoke and three-repository
  system proof passed;
- package runtime proof passed and confirmed that Python/operator evidence
  tooling is absent from the product package;
- both frozen policy digests remained exact.

The native graph and focused suites start no Factorio process. No WPR capture,
permit issuance, human verdict, accepted route or authority promotion occurred.

The supported raw Python suite was repeated after the full native graph was
present and passed.

GitHub PR 82 passed the complete duplicated push and pull-request validation
matrix and merged the exact reviewed head
`dc8e289079b862391520c1d031d8224827c0863d` into `dev` as
`be9bf23f9480a4fdafe3a6ad91528d28081e0c54`.

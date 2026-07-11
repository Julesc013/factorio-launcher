# Adding a command

1. Add or revise the command contract under `contracts/commands/`, including
   effects, risk, request/result shape, and refusal behavior.
2. Regenerate command metadata with the repository generator; never hand-edit
   generated catalogs.
3. Implement typed application behavior under
   `runtime/factorio/application/handlers/` and register it through the
   authoritative command graph.
4. Keep argument parsing and rendering in the frontend. Frontends call
   `runtime/client`; they do not include backend handler headers.
5. Add live result/refusal tests, goldens only where stable examples add value,
   and update `contracts/policy/test_impact.v1.json` when ownership changes.

Run command-contract, application-handler, client-boundary, affected, and full
promotion validation. A declared command is not available until dispatch and
runtime behavior agree; a golden file alone proves neither.

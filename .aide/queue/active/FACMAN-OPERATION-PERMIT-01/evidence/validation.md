# OperationPermit validation evidence

The contract-law slice passes:

- `py -3 tools/schema_validate.py`: 268 schemas.
- `py -3 tools/refusal_contract_check.py`: 242 refusal codes.
- `py -3 -m unittest tests.test_schema_tools tests.test_refusal_contract`.
- Strict validation through `tests.test_schema_tools`, including generated
  target truth after `py -3 tools/project_state.py --write`.
- `git diff --check`.

Gate 2 closeout validation remains recorded independently in
`docs/release/checkpoints/gate2-instance-spec-and-readiness-closeout.md`.

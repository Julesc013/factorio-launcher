# Changed Files

- `tools/m2_wu10_machine_acceptance_check.py` stops requiring sorted-key file
  bytes for transaction journals while retaining independent schema, chain,
  digest, and root-containment checks.
- `tests/test_m2_wu10_machine_acceptance.py` writes all eighteen generated
  journals in native field order and proves the fixture is not sorted-key
  canonical before deriving `EvidencePass`; all twelve negative controls stay
  active.
- Project status, generated state, compaction assertions, checkpoint docs, and
  the safety claim ledger record the blocked first result attempt and the
  policy-only correction with no acceptance result.
- AIDE task evidence preserves the fresh runner passes and verifier refusal.

# Observer-start repair activation

Gate 4C verdict attempt 01 closed `Inconclusive` after two fresh, separately
prepared operations produced the same refusal:

```text
permit_wrong_evidence:
independent observer was not active before process boundary
```

Both failures occurred before permit consumption and before process creation.
The reviewed harness did not retain the nested helper stderr, so this task must
first reproduce and preserve the exact diagnostic without launching Factorio.

The frozen policy, candidate selectors, authority boundary, and verdict law do
not change.

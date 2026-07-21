# Hermetic standalone Play policy changed-file intent

The WorkUnit now contains one frozen, digest-bound policy implementation:

```text
policy  facman.hermetic-standalone-play.2.0.77.windows-x64.v1
claim   factorio.hermetic_process_tree.v1
digest  6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2
```

Changed-file families are restricted to:

- six Factorio Play policy schemas under `contracts/schema/factorio/`;
- one immutable policy instance under `contracts/policy/factorio/`;
- the policy strict validator and focused negative-control tests;
- architecture, policy-index, and safety-claim documentation;
- canonical project truth, generated status projections, and truth tests; and
- the closed WorkUnit's exact hosted and clean-reproduction evidence;
- the Gate 4A closeout checkpoint and no-active-task promotion state; and
- one planned, deliberately unstarted implementation-candidate queue item.

Expected changes are restricted to policy, architecture, contract, release
truth, tests for those documents/contracts, and AIDE development state under
the task's declared `allowed_paths`.

No runtime, process execution, permit issuance, Factorio launch-provider,
Universal Setup, credential/network provider, signing, publication, or
host-mutation implementation is changed.

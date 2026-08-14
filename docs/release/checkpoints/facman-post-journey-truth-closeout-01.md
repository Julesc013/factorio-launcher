# Post-journey truth closeout checkpoint

Status: complete reviewed-checkpoint reconciliation on the exact PR #152
integration base. The repository now exposes one active product WorkUnit and
one dependency-ordered next WorkUnit without granting real execution or release
authority.

## Reviewed identity

- WorkUnit: `FACMAN-POST-JOURNEY-TRUTH-CLOSEOUT-01`
- branch: `task/facman-post-journey-truth-closeout-01`
- reviewed FacMan base: `dev@a4100f1ca6c79a9922697f7598b7df63cc7e8a34`
- reviewed base tree: `03e7cc7cbd5d2a168c69fac8a39f72007bc1495c`
- canonical ULK pin: `main@09f0639ab6529fba2f2aa22e9bf68e5eebed0553`
- canonical USK pin: `32488fc13bd2439f9f6e52e83a97f6da345a7650`

The tracked revision is reviewed checkpoint truth. It is not a continuously
updated observation of a checkout or provider remote. Live checkout observation
remains an out-of-tree result from `tools/current_checkout_observation.py`;
provider observations remain distinct from the exact consumed locks; generated
plan views identify their canonical source and freshness.

## Integrated journey slices

PR #151 integrated the fake execution-to-ULK journal bridge:

- task head: `9396055f4d7b7184d263fe833b46941207abc5e9`;
- dev merge: `1a7b69f09e9bcbc78f34d867014a1f855c0552fb`;
- merge tree: `7d8053f56fb0ff9e0d33cfbe489c1ef11c3497a6`.

PR #152 integrated presentation action-to-fake-session dispatch:

- task head: `c0d8b8a05912523ccbe8ca87ad773419ceecb30f`;
- dev merge: `a4100f1ca6c79a9922697f7598b7df63cc7e8a34`;
- merge tree: `03e7cc7cbd5d2a168c69fac8a39f72007bc1495c`;
- exact PR result: 32/32 checks passed;
- provider SDK run `31768923114`, attempt 2 passed after the first attempt's
  macOS artifact-service timeout; the substantive first-attempt provider proof
  had already passed and no source or evidence requirement was weakened.

The exact #152 merge-head workflow identities are recorded in
`release/index/project_status.v2.toml`. All seven required workflow groups
terminated successfully; provider SDK run `31776935197` completed its Windows,
Ubuntu, and macOS exact tracked-provider proof without a source repair or an
evidence exception.

## Planning reconciliation

The broad TUI WorkUnit and its separate closeout record are retained as
superseded history, not falsely marked complete. Their integrated implementation
is preserved, while unfinished release-blocking obligations are transferred as
follows:

- ordinary journey and cross-frontend semantic/fault equivalence belong to
  `FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01`;
- exact packaged accessibility, performance, and one-binary receipts belong to
  `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01`.

The resulting product sequence is:

```text
active  FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01
next    FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01
```

This consolidation does not relax same-binary TUI parity. It removes duplicate
WIP so CLI JSON, TUI, and WinForms close against one authoritative journey and
one exact candidate.

## Authority boundary

The integrated executor remains a test-only injected fixture. The production
application module has no launch executor. Therefore:

```text
real Factorio execution  false
Setup mutation           false
network acquisition      false
signing                   false
publication              false
release                   false
```

No Factorio process, private archive, Setup provider, signing key, publication
credential, or protected release ref is used by this closeout.

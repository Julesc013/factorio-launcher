# Changed files

The implementation accepted by this closeout was merged through PR #37 and is
recorded at exact `dev` revision
`6ec47046d1b1f4ab8bddfcc27bcec76a774ff305`.

- `runtime/factorio/installation/` binds reconciliation identity to canonical
  current evidence and desired state, decodes desired-state values into strong
  internal types, emits closed-vocabulary effects, and exposes explicit source
  trust and evidence freshness.
- The five installation-model schemas carry canonical digests, provider and
  policy revisions, revalidation requirements, source trust, and zero-write
  guarantees without introducing an apply contract.
- Native and CLI tests independently reconstruct digests, cover the supported
  installation classes and authority matrix, and snapshot installations,
  sources, workspaces, and missing-workspace paths.
- Installation architecture and active umbrella evidence state the bounded
  read-only result and preserve every deferred mutation boundary.
- This follow-up changes only project truth, checkpoint documentation, AIDE
  WorkUnit disposition, and truth-regression expectations. It adds no runtime,
  command, schema, refusal, provider, credential, process, signing, or
  publication authority.

The original umbrella WorkUnit is deliberately not marked complete. Its
remaining authenticated-source and mutation lifecycle is transferred to
`FACMAN-MANAGED-INSTALL-RECONCILIATION-01`.

# Remaining risks

- The SDK candidate proves production-capable explicit consumption but is
  intentionally not an active provider truth. The workspace lock still
  consumes ULK `7fc25340623131ba86c08dca4fb8a43b18a4520d` and USK
  `3048128963dc718a7c38c1cfcdda9e813a23b0db`.
- The authored release-provider lock still names ULK `719a3ec240831547071d69098e1fe8c76f327fb7`
  and USK `7f8f2baa14e78b0329db8eef8ac872818c4cf30d`. Strict release coherence must
  remain fail-closed until the separate atomic reconciliation.
- Provider SDK identities and inventories are target- and linkage-specific.
  Pin reconciliation must consume the exact Linux, Windows, and macOS evidence
  records rather than treating one host's package bytes as universal.
- Source mode remains required for rollback and source closure. Completion of
  this WorkUnit does not authorize a heuristic SDK fallback, deletion of
  source mode, or preference for ambient package registries.
- GitHub artifacts expire after fourteen days. The durable out-of-tree copies
  under `D:\Projects\Factorio\Evidence\pr126-1a8bcbf-hosted` must remain in
  custody until superseded by reviewed reconciliation evidence.
- The GitHub runner reports a non-blocking Node.js action deprecation warning
  for `actions/upload-artifact@v4`; it does not alter the generated evidence,
  but the workflow dependency should be updated when its maintained release
  changes.
- Successor source closure remains blocked on atomic provider reconciliation,
  immutable route v2, and a qualified Windows closure host. PR #123's original
  six commits remain untouched.
- The work creates no Factorio execution, observer, prepare, permit, Setup
  mutation, signing, publication, support, route capability, route promotion,
  or protected-branch authority.

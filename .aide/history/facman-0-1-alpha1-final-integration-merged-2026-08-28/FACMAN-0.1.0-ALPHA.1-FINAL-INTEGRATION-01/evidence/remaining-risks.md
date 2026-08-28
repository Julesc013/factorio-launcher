# Remaining risks and gates

- PR #191 and its corrected source-bound package refresh are integrated by
  normal merge commit `06f0f7c9084ad90c59b09c5691847791ddc7dd85`;
  all 20 protected merge-head checks, including CodeQL and the full provider
  matrices, passed. Final human-test artifacts must still be rebuilt from the
  post-closeout protected `dev`, not reused from the PR head or synthetic ref.
- A real Play route remains unaccepted, so the candidate is not a public
  playable alpha.
- Direct human CLI, TUI, WinForms, and accessibility receipts remain outside
  machine qualification and must be completed before their respective gates.
- Signing, publication, support promotion, tagging, route promotion, and main
  promotion remain separate actions requiring their defined gates. Tagging
  also requires the currently absent active no-bypass alpha-tag ruleset.

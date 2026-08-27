# Remaining risks and gates

- The evidence-only closeout head still requires a source-revision-bound
  package refresh and hosted protected-dev checks, including CodeQL; those
  receipts must be attached to the pull request before integration review.
- A real Play route remains unaccepted, so the candidate is not a public
  playable alpha.
- Direct human CLI, TUI, WinForms, and accessibility receipts remain outside
  machine qualification and must be completed before their respective gates.
- Signing, publication, support promotion, protected integration, tagging, and
  main promotion remain separate actions requiring their defined gates.

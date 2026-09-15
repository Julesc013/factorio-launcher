# Remaining qualification and product risks

This checkpoint does not close the WorkUnit or qualify an Alpha release.

- The pinned Universal Setup provider cannot publicly finalize every inspected
  interrupted transaction. Rollback is admitted only after an exact preview and
  revalidation; other recovery actions remain an explicit operator/provider
  blocker and never replay apply.
- The native tests use an injected provider and the ownership fixture. A fresh
  packaged current-source run still must exercise real Start Menu and registry
  effects, interruption, restart, repair, and removal on the declared Windows
  target.
- Hosted Windows, Linux, and macOS checks have not yet qualified the eventual
  integration commit. Historical runs remain evidence for their original source.
- The existing external MSVC root reports the Visual Studio warning against
  placing intermediate output below the Windows temporary directory. The build
  and selected tests pass, but the later package qualification should use the
  marker-owned task root.
- `workspace_hygiene.py doctor --measure --max-task-roots 10` previously could
  not read an older task-root `manifest/resolution` path. No cleanup or resource
  ceiling increase was performed.

## 2026-09-15 managed uninstall recovery boundary

- Universal Setup public recovery finalization remains `install_local` only.
  FacMan therefore projects only an already completed uninstall journal and
  never invokes provider finalize, recovery apply, or rollback for uninstall.
- An incomplete, corrupt, mismatched, unsafe, or nonterminal provider journal
  remains recovery-required for later provider/operator resolution. FacMan does
  not infer completion or replay uninstall.
- The qualification uses owned synthetic install roots and provider state. It
  does not qualify recovery against a real user installation or a packaged
  release candidate.
- `FACMAN-0.1-ALPHA6-MANAGED-INSTALL-RECONCILIATION-01` remains active; this
  operation-specific recovery checkpoint does not close or supersede it.

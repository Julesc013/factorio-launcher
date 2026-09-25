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

## 2026-09-16 integration boundary

PR #292 and its protected promotion integrate the qualified install, repair,
uninstall, cache-custody and native-effect recovery slice. The WorkUnit remains
active because its canonical acceptance also includes update recovery.
Independent FacMan update/downgrade, locked-file replacement, and restart
handoff are being advanced by active
`FACMAN-0.1-ALPHA6-SELF-MAINTENANCE-01` without transferring or narrowing this
WorkUnit's acceptance.

## Shared candidate-workflow risk

The optional two-package self-maintenance job is source preparation only until
it runs against an exact alpha.6 candidate and lower source-distinct alpha.5
baseline on the declared Windows host. It does not qualify the existing native
recovery interruption/restart cases, and it does not claim chain-aware removal.

## 2026-09-26 installed-use scope after Windows epoch integration

PRs #330, #331, #333, #337 and #335 now provide source-distinct Windows epoch
repair, continuation, rollback/reapply and removal evidence; candidate
`36163129508` passed its real current-user transition. This supersedes the
earlier Windows source-preparation-only statement above. The WorkUnit remains
active: Linux `.run` source-distinct replacement still lacks a recoverable
transaction chain, and the macOS PKG adapter remains installation-only. The
Linux ownership correction recorded in `validation.md` needs exact-head
produced-package qualification before integration.

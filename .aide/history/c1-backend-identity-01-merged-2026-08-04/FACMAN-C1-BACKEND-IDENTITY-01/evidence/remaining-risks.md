# Remaining risks

- The actual packaged GUI `OpenProduction` running-image binding is
  Release-compiled and structurally checked, but was not behavior-executed as
  the GUI. The executable harness exercises the same package and child-image
  laws through the private package opener without granting product execution.
- Windows profile ancestors that refuse a retained directory handle are
  no-reparse audited and re-resolved; the package root and all descendants are
  strictly handle-held. Network/shared filesystems are unproven.
- The standalone native verifier is not a single retained snapshot. POSIX
  executable discovery still trusts caller-supplied `argv[0]`; standalone
  CLI/TUI, Linux, and macOS identity stability are not promoted here.
- SHA-256 closure proves consistency, not publisher authenticity. The local
  package is source-dirty, unsigned, unpublished, and not a release candidate.
- Exact clean task-head reconstruction and hosted validation remain review
  evidence after the final tracked commit; they cannot be inferred locally.
- Workspace-root ownership remains a separate future WorkUnit. `run.execute`
  remains unavailable and no Factorio Play, permit, successor route, Setup
  mutation, repin, signing, publication, or human-verdict authority exists.

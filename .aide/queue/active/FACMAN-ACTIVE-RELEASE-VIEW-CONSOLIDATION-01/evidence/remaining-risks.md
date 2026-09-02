# Remaining risks

- This consolidation makes release intent coherent; it does not qualify new
  candidate bytes. The last machine-qualified bytes remain the exact final
  Alpha.5 candidate recorded by the predecessor receipt.
- The predecessor is integrated as canonical `dev` commit
  `f99d96e002f5af519824942a1f8b74bcc26d96f8`. This WorkUnit has been
  forward-restacked onto that exact commit and still requires exact-head hosted
  checks, review, and authorized protected integration.
- Repository identity remains an explicit release-maintainer decision. No
  repository rename may be inferred or performed, and identity must remain
  stable from Beta.1 through stable 0.1.0 once chosen.
- Windows x64 WinForms/.NET Framework 4.8 remains the reference product.
  macOS AppKit and Linux GTK3 are selected experimental previews, not claims of
  semantic or human parity. Qt6, WinUI, SwiftUI, universal2, and broader
  Wayland work remain future admission programmes.
- Standalone CLI, TUI, toolkit, SDK, maintenance, and adapter artifacts remain
  inspectable catalogs but are not current Beta.1 release obligations.
- Real Factorio Play/session/Last Run, managed-install apply/recovery, clean
  desktop install/upgrade/uninstall, accessibility/usability, Linux/macOS human
  acceptance, signing, notarization, tagging, publication, and support approval
  remain later operator/human gates bound to exact candidate bytes.
- The bounded full R37 performance corpus remains opt-in. Exact packaged
  performance, extended adversarial-path/security, durability, and
  fault-injection acceptance remain future gates.
- Five Windows symlink negative controls remain unsupported under the current
  token. Their validators fail closed, and no required obligation was skipped.

Accordingly, this WorkUnit is ready for review and protected integration. The
repository is not yet ready for Beta.1 tagging, publication, or a support
claim.

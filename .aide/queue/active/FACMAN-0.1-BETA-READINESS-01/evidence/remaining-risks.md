# Remaining Risks

- The non-publishing product-candidate workflow still needs hosted Windows,
  macOS, and Linux execution, artifact retrieval, and independent bundle
  verification. Local promotion evidence cannot substitute for that matrix.
- WinForms has a clean .NET Framework 4.8 build, and GTK3 has hosted PR
  merge-ref package/runtime and external AT-SPI proof. Human usability and
  accessibility acceptance, GTK3/AppKit semantic convergence, and the full
  product-candidate proof remain pending. Qt6, WinUI, and SwiftUI remain
  post-beta placeholders rather than completed frontends.
- Migration support remains deliberately bounded: there is no public recovery
  or rollback command, and recovery-required states can still require manual
  remediation.
- Content and world portability records and the local content-addressed cache
  remain internal foundations. Workspace/startup integration, transactional
  offline reconstruction, WorldBundle workflows, and garbage-collection
  apply/recovery are not complete.
- Managed installation authority and Play authority remain externally blocked.
  Exact packaged hardware performance baselines also remain pending.
- Apple silicon qualification, broader Linux/Wayland coverage, and deferred
  network, plugin, and daemon systems are outside the current completed scope.
- Final release packaging still needs the versioned checksum/evidence
  finalizer and durable hosted provenance. Unsigned candidates depend on
  GitHub artifact custody until authenticity controls are approved.
- Human acceptance, accessibility approval, signing/notarization, beta
  tagging, publication, and support readiness all require later evidence and
  explicit operator authority. None is implied by the local pass.

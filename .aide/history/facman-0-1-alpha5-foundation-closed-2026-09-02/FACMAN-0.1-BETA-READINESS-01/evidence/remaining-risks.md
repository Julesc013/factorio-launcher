# Remaining Risks

- Exact non-publishing candidate execution is no longer a remaining risk: run
  `33576140943`/attempt 1 passed all five jobs at source
  `a7a518dbfe2a6d54da7b9c84fbd318300265e31d`, and its final artifact verified
  as exactly 14 files. That proof is deliberately unsigned, unpublished, and
  non-authorizing; it does not convert candidate custody into release status.
- WinForms has a clean .NET Framework 4.8 build, and GTK3 has hosted PR
  merge-ref package/runtime and external AT-SPI proof. Human usability and
  accessibility acceptance and GTK3/AppKit semantic convergence remain
  pending. Qt6, WinUI, and SwiftUI remain deferred lanes/placeholders rather
  than completed or beta-qualified frontends.
- Migration support remains deliberately bounded: there is no public recovery
  or rollback command, and recovery-required states can still require manual
  remediation.
- Content and world portability records and the local content-addressed cache
  remain internal foundations. Workspace/startup integration, transactional
  offline reconstruction, WorldBundle workflows, and garbage-collection
  apply/recovery are not complete.
- Managed-install and Play journeys still require accepted human/external
  evidence. Exact packaged hardware performance, security, durability,
  adversarial path/archive, and fault-injection qualification remain pending.
- Apple silicon qualification, broader Linux/Wayland coverage, and deferred
  network, plugin, and daemon systems are outside the current completed scope.
- Final release packaging still needs the versioned public checksum/evidence
  finalizer and durable hosted provenance. The verified unsigned candidate
  remains subject to GitHub artifact retention and the preserved external
  verification root until authenticity controls are approved.
- Human GUI acceptance, accessibility approval, accepted Play/install
  journeys, signing/notarization, beta tagging, publication, and support
  readiness all require later evidence and explicit operator authority. None
  is implied by either the local pass or candidate pass.

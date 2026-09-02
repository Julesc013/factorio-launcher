# Remaining risks

- The hosted proof qualifies only exact candidate revision
  `a7a518dbfe2a6d54da7b9c84fbd318300265e31d`. The closeout revision and every
  later revision require a fresh product-candidate run; tree equality is not a
  substitute for revision-bound evidence.
- The twelve C1 journeys still need their required human closure. In
  particular, real Play/session/Last Run, managed-install application and
  recovery, and public migration recovery are not accepted product behaviour.
- WinForms is machine-qualified at .NET Framework 4.8, but human usability and
  accessibility verdicts remain pending. GTK3 and AppKit have native package
  lanes and bounded preview proofs, but not full semantic/human parity with the
  Windows shell.
- Migration, content-set, world-bundle, save, cache, and CAS/GC foundations are
  contract-backed and tested, but several public workflow integrations,
  transactional offline reconstruction paths, and recovery/apply surfaces
  remain intentionally incomplete.
- Exact packaged performance at larger supported scales, packaged security and
  adversarial-path evidence, and package-level durability/fault-injection
  acceptance remain future release gates. The bounded full R37 performance
  corpus is optional and was not enabled in this local profile.
- The verified candidate is unsigned and unpublished. Signing, macOS
  notarization, immutable beta tagging, public checksums/provenance custody,
  release publication, and support approval require explicit later authority.
- Apple Silicon/universal2, broader Linux/Wayland qualification, Qt6 product
  admission, WinUI, SwiftUI, public extension/plugin SDKs, daemon/network and
  account services, automatic updates, server management, and Steam-integrated
  execution remain deferred. Pulling them into 0.1 without their independent
  admission and evidence would weaken, rather than complete, the release.
- Hosted artifacts are retention-bounded. The exact verified bundle must remain
  in durable local custody until a successor candidate and approved public
  provenance path supersede it.

Accordingly, the repository is ready for this closeout integration and a fresh
successor candidate run. It is not yet ready for beta tagging, publication, or
a support claim.

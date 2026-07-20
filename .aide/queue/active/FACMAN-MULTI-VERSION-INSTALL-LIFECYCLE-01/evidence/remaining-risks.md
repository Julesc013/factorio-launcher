# Remaining risks

- Factorio's official Space Age installers reuse one uninstall registration
  identity. The exact 2.1 key was restored, so 2.0 has a genuine local
  uninstaller but is not a second Add/Remove Programs entry.
- Directly launching `D:\Games\Factorio\2.0\bin\x64\factorio.exe` uses the
  official system-data configuration and can share `%APPDATA%\Factorio`.
  The `factorio-2-0` FacMan instance avoids that route with explicit arguments.
- The original portable tree remains as a roughly 5.05 GB rollback copy. The
  4.2 GB downloaded ZIP and extracted split installer also remain; no source or
  rollback material was deleted automatically.
- The publisher setup auto-launched Factorio after copying files. The exact
  newly created process was stopped before registry restoration. Five shared
  AppData files show operation-window writes; they were not reverted because
  there was no safe pre-operation snapshot. A general setup adapter must model
  or suppress publisher post-install processes and snapshot declared external
  state before apply.
- Foreign-tree repair, move, reinstall, update, and uninstall are not yet
  general product mutations. They require source authentication, reviewed
  ownership adoption/replacement, transaction recovery, and Universal Setup
  apply authority.
- Installation model v2 is currently a read-only projection over the compatible
  v1 stored record. Source identity for the live 2.0.77 installation is not yet
  durably bound, filesystem capabilities are revalidation requirements rather
  than apply proofs, and no v2 persisted-record migration is enabled.
- Reconciliation plans are advisory provider inputs. They expose blockers,
  risks, ordered responsibilities, and rollback policy, but deliberately have
  no apply command until authenticated source inspection, exact staged closure,
  dependent-instance impact, interruption recovery, and provider gates exist.
- Real Factorio Play remains disabled. The execution foundation is fake-process
  proven, but hermetic standalone Play and Steam-aware Play require their own
  reviewed gates.
- The work unit remains active because the full lifecycle objective is larger
  than the completed discovery, preservation, and one-host replacement
  milestone.

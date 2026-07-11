# Remaining Risks

- The frozen R3.2 artifact digest is retained from the revision-pinned public
  checkpoint; that exact artifact file is not present in the current local
  build tree and was therefore not rehashed in this WorkUnit.
- The archive dependency has not yet been selected or admitted.
- Production archive handling, transactional data transfer, recovery,
  diagnostic export, and the Linux package remain future R3.3 WorkUnits.
- Real Factorio isolation and `run.execute` remain separately human-gated.

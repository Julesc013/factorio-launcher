# Remaining risks

- Archived records are immutable by lifecycle policy and hash checking, but Git still supplies the authoritative tamper-evident history after commit.
- The imported AIDE pack may overwrite target-local CLI extensions during a future pack upgrade; upgrade review must preserve `aide_lifecycle.py` integration.
- Real Factorio acceptance remains operator-only and pending.
- Target CI, signing, notarization, publisher authenticity, and publication remain separate gates.

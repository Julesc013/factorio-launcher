# Remaining risks

- The ULK session journal is integrated only on ULK `dev@85df03b`; it is not on
  canonical ULK `main` and FacMan still consumes `1cafe405`.
- `ULK-SESSION-LAST-RUN-PROMOTION-01` must qualify and promote the exact subset
  before `FACMAN-ULK-SESSION-PIN-ADOPTION-01` can start.
- Frontend-local Last Run caches remain on the unchanged production path until
  the atomic global authority cutover. They must not survive as fallback
  authority after adoption.
- The exact first route still requires the 2.0.77 versus retained 2.1.14 corpus
  decision and a separately provisioned clean Windows proof host.
- No current evidence qualifies real Factorio Play, managed installation,
  signing, publication, support, or a public release.
- AppKit and GTK remain experimental compatibility shells. They do not block
  the Windows preview, but after the Last Run cutover they may only read the
  backend authority or show an explicit unavailable state.

# Evidence Summary

Result: local promotion validation, hosted PR merge-ref GTK repair proof, and
the exact non-publishing Windows/macOS/Linux product candidate passed. Human
acceptance and every release-authority action remain pending.

The alpha.5 foundation completed the full local promotion obligation profile:

- native tests: 41/41 passed;
- WinForms .NET Framework 4.8 build: 0 warnings and 0 errors;
- Python tests: 1,417 run with 0 failures, 0 errors, and 9 classified skips;
- skip classes: optional 2, unsupported 5, not applicable 2, required blocked
  0, and unknown 0; and
- strict validation: 399 schemas, 127 commands, 247 refusal codes, and 128
  goldens passed.

The first PR run also exposed and localized a GTK proof-only metadata/transport
fixture drift. The repair removes the copied window title, binds the external
AT-SPI assertion to generated product metadata, and makes the mock response
conform to the strict correlated v2 transport envelope. Focused regression and
strict validation pass locally. PR 227 merge ref
`a5cc990d0a684a24f681eed9a0f10a2e09071d54`, associated with repair head
`f6546d2d24bce1fa198f7e923d0a6a73e9384356` and its identical tree
`b6cf55caffdeeeacd3a1856e30143dba727c0d4b`, also passed hosted
`linux-native` job `99929032838` in run `33529589182`, including the external
AT-SPI package proof.

The candidate required three bounded failure/repair chains before the pass:

- the first manual dispatch returned HTTP 422 and created no run; its timestamp
  and response body are unknown and are not invented. Runner-dependent root
  binding was repaired by `c18d6743` and synchronized by `d38dbc30`;
- run `33557664813`/attempt 1 at `67e25b38130a2f939bdbf67a2623bb71a41ab0bd`
  exposed the repository-module import defect repaired by `10da832e`; and
- run `33567017006`/attempt 1 at `680c22aa0a457668475d8087ee28b9cb6e0791d6`
  exposed the Windows checkout-include and macOS symlinked-temporary-root
  defects repaired by `f43049d4`. Its successful Linux lane produced artifact
  `9823610585`, digest
  `sha256:e46a2e644613d376f59cbef1491407bb72709790df8f90e661c3e3158b6693ea`.

Final run `33576140943`/attempt 1 passed at exact source
`a7a518dbfe2a6d54da7b9c84fbd318300265e31d`, tree
`1ebcd2b230ed188e021880ffa4c438de2ede655b`. Its five successful jobs were
`100080412106`, `100080456660`, `100080456693`, `100080456726`, and
`100081901409`. Its four artifacts were:

- final `9826850751` -
  `sha256:2afe4529f056ac4400352400418e5cede776146e9ef803aa4901cc76944f71c5`;
- Windows `9826842304` -
  `sha256:a2b58ef796dfc7daf35d0993e02bdf5807937cf1c3dea5ae035fd4d45b510f82`;
- macOS `9826791575` -
  `sha256:530533736e47233f0f005a27b576760261bef44a7b3ace19c386047a7804bf8b`;
  and
- Linux `9826768803` -
  `sha256:6c8f0854d863de5bea7d9b5d97ad74be3c8720020c815b531b43835987065e0d`.

The final artifact independently verified as exactly 14 files under the
marker-owned external Beta root
`C:\Users\Jules\AppData\Local\FacMan\Development\repositories\factorio-launcher-5db2844e2f29\tasks\facman-0.1-beta-candidate-33576140943-20260902t0046z\bundle`.
The candidate manifest is `pass` but grants no tag, release, publication,
signing, or support authority. This is machine-qualification evidence, not a
beta-release or human-acceptance verdict.

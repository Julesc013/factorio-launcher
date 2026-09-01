# Evidence Summary

Result: local promotion validation and the hosted PR merge-ref GTK repair proof
passed; product-candidate and release authority remain pending.

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

This is local machine-qualification evidence, not a beta-release verdict. The
manual hosted Windows, macOS, and Linux product-candidate workflow, semantic
GUI convergence, human accessibility review, signing, tagging, publication,
and support readiness have not yet been completed.

# Changed files

## Production-capable provider consumption

- `CMakeLists.txt`, `cmake/FacManProviders.cmake`, and
  `cmake/FacManInstall.cmake` define a distinct, exact
  `FACMAN_PROVIDER_SDK_CONSUMPTION_CANDIDATE` class. Source,
  installed-static, and installed-shared inputs remain closed choices and
  downstream code continues to consume FacMan-owned wrapper targets.
- `tools/provider_sdk_consumption.py` builds, installs, relocates, packages,
  and semantically probes seven source/SDK/runtime modes. It also exercises
  seven exact refusal controls and writes one non-authorizing observation.
- `tools/provider_conformance.py`, `tools/integration_source_observation.py`,
  and `tools/package/pipeline.py` distinguish the SDK candidate from Phase-A
  conformance and from tracked/release provider adoption.
- `contracts/schema/release/provider_sdk_consumption.v1.schema.json` closes
  the observation shape, pass/rehearsal distinction, required mode set,
  negative controls, and all-false authority table.
- `.github/workflows/provider-sdk-consumption.yml` binds exact FacMan and
  canonical provider heads and proves the candidate on Linux x64, Windows
  x64, and macOS Intel without uploading provider source trees or product
  payloads.

## Tests and generated identity

- `tests/test_provider_sdk_consumption.py` covers classification, schema,
  candidate identity, source independence, runtime closure, refusal controls,
  and authority.
- Provider-mode, semantic, package, integration-observation, and backend
  identity tests now cover the distinct SDK-consumption candidate.
- Generated build identity and WinForms command-catalog projections record
  `provider_sdk_consumption_candidate` without claiming adoption or release
  coherence.

## Normal tracked-source compatibility repair

- The candidate-only provider child-install exclusion is scoped to the SDK
  candidate. Normal tracked source builds retain the existing ULK/USK runtime
  package closure.
- A Windows tracked-source reproduction passed all nine built-package
  artifact tests with `ulk.dll`, `usk.dll`, `facman.exe`, and
  `flb_factorio.dll` present.

## Planning and lifecycle closeout

- The durable checkpoint, canonical plan, project state, roadmap, AIDE queue,
  and generated summaries transition only
  `FACMAN-PROVIDER-SDK-CONSUMPTION-01` to complete.
- `FACMAN-PROVIDER-PIN-RECONCILIATION-01` becomes dependency-ready but remains
  inactive until this reviewed branch is integrated into `dev`.
- `workspace_lock.v1.toml`, `providers.lock.v2.toml`, and immutable successor
  route v1 remain byte-identical to the accepted base.

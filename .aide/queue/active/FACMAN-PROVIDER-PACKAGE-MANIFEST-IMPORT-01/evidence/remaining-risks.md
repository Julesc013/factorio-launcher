# Remaining risks

- Canonical ULK adoption cannot run until PR #16 is merged by an independent
  integrator and its actual protected `main` merge package is rebuilt.
- The local full native matrix is not authoritative on this host: canonical USK
  emits an existing MinGW-only unused-function warning under `-Werror`.
  The focused MSVC presentation comparison passes, but hosted Linux, Windows,
  and macOS checks remain required before integration.
- The importer must be refreshed against the actual protected FacMan `dev`
  merge after PR #154 is integrated; no anticipated FacMan merge identity may
  be adopted.
- No public tag, release, signing, publication, support activation, repository
  rename, Setup mutation, or live Factorio installation mutation is authorized.

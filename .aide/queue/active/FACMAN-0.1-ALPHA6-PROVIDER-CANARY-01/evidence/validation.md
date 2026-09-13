# Validation

Current result: hosted provider conformance passes; WorkUnit closeout remains
pending review of the final SDK-consumption observation.

## Bound hosted conformance

- FacMan source `081a342a498273dbbd5aa91a7bed234dcd987ffc`, tree
  `f47600447ae36b67e35d077fa05e94817f506a8d`.
- Hosted workflow run `34762715681`.
- Pinned Universal Launcher `5479939ca5cbc9ee0f901608a92012778b4752ae`,
  tree `7728e4d415539a0f24e6f17aa7d22be00cc99d80`.
- Pinned Universal Setup `d2a2aae7e61c47035c92334b0522143b4fea3880`,
  tree `291d63214cdd0cd3d15c809de5744ee3514fb2b2`.
- Linux, macOS, and Windows each passed seven consumption modes: source
  static/shared, installed static/shared, relocated installed static/shared,
  and private runtime.
- Interrupted recovery passed on all three platforms. All recorded negative
  controls refused and tracked provider locks remained unchanged.
- Independent non-authoring GPT-5.6 Sol review parsed all eight observations
  with zero findings and concluded
  `PASS_HOSTED_PROVIDER_CONFORMANCE_NOT_ADOPTION`.
- Review receipt SHA-256:
  `4ba6b6e8fe5dc51d72d6bd8142bb082b497841e65703fb13184b68894d2362d2`.

## Pending final closeout check

Provider SDK-consumption run `34762715690` is bound to the same FacMan source
tree. Linux job `103742041863` and Windows job `103742041928` passed. macOS job
`103742041792` is still running its tracked reconciled provider proof. Its
produced observations must be retained and reviewed before AIDE verify, review,
and close are run.

Repository lifecycle, plan-generation, project-state, focused unit, strict,
AIDE Lite, commit-message, and diff checks will be recorded after that final
receipt is available. No current statement treats the pending run as a pass.

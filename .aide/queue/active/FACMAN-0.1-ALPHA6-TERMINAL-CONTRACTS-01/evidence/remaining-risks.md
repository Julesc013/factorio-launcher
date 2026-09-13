# Remaining risks

- PR 279's exact protected integration and hosted Windows, Linux and macOS jobs passed. Those jobs are runner-backed machine evidence, not human hardware or UX acceptance.
- The CLI host's 16 MiB response ceiling is implemented, while this slice directly exercises the 1 MiB request ceiling and the process client's 1 MiB child-output refusal. A synthetic 16 MiB product response was not manufactured solely to mirror the constant.
- This slice does not execute Factorio, sign packages, publish a release, or provide human UX acceptance. Those acceptance cells remain with their owning WorkUnits.

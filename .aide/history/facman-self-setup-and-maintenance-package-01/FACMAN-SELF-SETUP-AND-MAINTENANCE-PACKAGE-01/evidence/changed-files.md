# Changed files

The WorkUnit changes only the FacMan repository and keeps Universal Launcher
and Universal Setup as pinned, independently governed providers.

- \`apps/setup/\` and \`runtime/self_setup/\`: thin Windows self-setup shell and
  USK-backed install, verify, repair, and uninstall orchestration.
- \`tools/self_setup_package.py\`, \`tools/alpha2_qualification.py\`, and
  \`tools/alpha2_release_assets.py\`: deterministic package, three-root
  qualification, and exact draft-asset assembly.
- \`tests/\`: lifecycle, deterministic-package, release-inventory, version
  transition, and plan-fixture coverage.
- \`.github/workflows/ci.yml\`: external WinForms package root, setup build,
  real packaged lifecycle, and bounded seven-day evidence artifact.
- \`release/index/\`, generated version/catalog surfaces, and project-state
  views: allocate 0.1.0-alpha.2 while retaining alpha.1 as immutable history.
- \`docs/product/facman_self_setup.md\` and
  \`docs/release/checkpoints/facman-self-setup-and-maintenance-package-01.md\`:
  operator contract, exclusions, lifecycle, and release boundary.

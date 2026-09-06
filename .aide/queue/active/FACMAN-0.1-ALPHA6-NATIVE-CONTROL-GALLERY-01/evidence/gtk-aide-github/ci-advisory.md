# AIDE GitHub CI Advisory

- schema_version: aide.github-ci-advisory.v0
- generated_by: aide-lite
- repo_id: julesc013/aide
- workflow_installation: false
- workflow_file_written: false
- github_api_mutation: false
- network_calls: false
- provider_or_model_calls: false
- preview_only: true

## Recommended Jobs

- aide-harness-validate: `py -3 scripts/aide validate`
- aide-lite-validate: `py -3 .aide/scripts/aide_lite.py validate`
- aide-lite-test: `py -3 .aide/scripts/aide_lite.py test`
- aide-lite-eval: `py -3 .aide/scripts/aide_lite.py eval run`
- commit-check: `py -3 .aide/scripts/aide_lite.py commit check --latest`
- changelog-validate: `py -3 .aide/scripts/aide_lite.py changelog validate`
- git-policy: `py -3 .aide/scripts/aide_lite.py git policy`
- github-validate: `py -3 .aide/scripts/aide_lite.py github validate`
- pack-status: `py -3 .aide/scripts/aide_lite.py pack-status`
- secret-scan: `targeted secret scan`

## Recommended Triggers

- pull_request
- push_to_main
- push_to_dev

## Boundary

Q35 recommends CI gates only. It does not create `.github/workflows`, activate
CI, mutate GitHub settings, or publish releases.

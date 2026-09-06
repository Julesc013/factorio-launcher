# AIDE GitHub Branch Protection Plan

- schema_version: aide.github-branch-protection-plan.v0
- generated_by: aide-lite
- repo_id: julesc013/aide
- current_branch: task/facman-0-1-alpha6-native-control-gallery-01
- current_branch_role: task
- github_api_mutation: false
- branch_protection_applied: false
- workflow_file_written: false
- preview_only: true

## Branch Targets

- main: role=canonical; present=true; force_push=false; deletion=false
- dev: role=integration; present=true; force_push=false; deletion=false
- release/*: role=release; present=false; force_push=false; deletion=false
- hotfix/*: role=hotfix; present=false; force_push=false; deletion=false

## Required Status Checks

- aide-validate
- aide-lite-validate
- aide-lite-test
- aide-lite-eval
- commit-check
- changelog-validate
- git-policy
- github-validate
- pack-status
- secret-scan

## Boundary

This is an advisory plan. Q35 does not call GitHub APIs, create branch
protection rules, write `.github/workflows`, push branches, create tags, or
publish releases.

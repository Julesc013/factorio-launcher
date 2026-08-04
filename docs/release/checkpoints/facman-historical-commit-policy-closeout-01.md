# Historical commit-policy closeout

Status: complete; forward-only enforcement active

Date: 2026-08-05

WorkUnit: `FACMAN-HISTORICAL-COMMIT-POLICY-CLOSEOUT-01`

Published history is not rewritten to repair commit messages. The following
pre-policy commits are the complete newly sealed exception set; each exception
is bound by its full immutable object ID and exact subject in
`.aide/commit_policy_baseline.toml`:

| Commit | Exact subject |
| --- | --- |
| `451dc6376d52ac2ddaf82c07ee95e423deec0829` | `land: task/c1-backend-identity-01 into dev` |
| `6538e519af3be221614879cc7f3323b9835dfae6` | `promote: dev into main` |
| `0da078ff89e9d5e85bb8a98c1b7d4f546c4757bd` | `Promote dev after UNIVERSAL-BRANCH-MODEL-RATIFICATION-01` |
| `9766c01afae3ef6b70a4e55b53ade1db479e254c` | `merge: reconcile provider contract wave` |
| `e21b200ee7e6a8f1364399c592bbd3539d2b6291` | `promote: provider contract wave reconciliation` |
| `9461c6ae7e733446ddaa719d89d89a39f9147e71` | `merge: workspace root authority and provider closeout` |
| `5dfef289aa98a1a8df62b8e32b81e1743d2aeaad` | `promote: workspace root authority and provider closeout` |

The policy boundary is
`5dfef289aa98a1a8df62b8e32b81e1743d2aeaad`. Wildcard exceptions, subject-only
exceptions, prospective exemptions, and history rewriting are forbidden. All
later commits must satisfy the current structured commit policy.

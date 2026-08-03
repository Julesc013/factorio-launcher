# Revalidation-03 stage binding

State: `staged_not_prepared`

```text
qualification digest
49732ad3a785a1341f642b9cfd99c01a78bbb199f6a3ef8b88b8a7acd79d9868

staged-candidate digest
b2e8335fa372e8f796af939e426a0cc3c7f98a68497e8fe9326e8b7f1da5a35c

qualification filename
artifacts\qualification-binding.v3.json

historical v2 filename
absent

stage inventory
16 files / 63,878,491 bytes / 0 reparse points

launch 1
gate4c-instance-isolated-6f6834a2-7773-49bb-85a4-985b555caf39

launch 2
gate4c-instance-isolated-d5e2105a-46ba-4edb-a757-ce05657b0361
```

The exact source clones remained clean, the protected process inventory was
empty, and WPR was idle after stage validation.

No explicit revalidation-03 operator exists yet. No observer self-test,
prepare, baseline, observer capture, permit, Factorio process, human verdict,
or route authority exists.

## Repository closeout validation

```text
focused truth/plan/AIDE-compaction tests       PASS 36
affected native tests                         PASS 1/1
affected Python/package/truth tests            PASS 63
full native CTest                              PASS 57/57
full promotion Python suite                    PASS 567
required-blocked skips                         0
unknown skips                                  0
optional skips                                 7
unsupported skips                              2
strict validation                              PASS
schema validation                              PASS 304
source-format validation                       PASS
project-state generation/validation            PASS
canonical plan generation/validation           PASS
AIDE queue state                               PASS
AIDE tier model                                PASS
```

The affected test planner initially built only `facman_client_smoke` while
admitting package-runtime tests that require the complete install graph. That
run failed before package assertions because `flb_factorio.dll` was absent and
is not acceptance evidence. Completing the disposable build graph made the
identical affected set pass.

The first two full promotion runs executed all 567 Python tests without test
failures but correctly kept the promotion gate closed because the default
all-target build omits `fl_archive_probe`, `fl_archive_metadata_fuzz`, and
`fl_archive_plan_fuzz`, and external builds are not discovered automatically
by the archive tests. Those runs remain non-acceptance evidence.

The final run explicitly built and bound those exact three disposable
executables. Its obligation record reports `gate_passed=true`, zero required
or unknown skips, and the counts above. This reproduces the separate
developer-runner gap already documented by the stage-handoff repair; it does
not change archive code, evidence policy, or the staged candidate.

The AIDE changed-file verifier reported no errors and warning-only scope
review for the deliberate queue-to-history move and regenerated truth
surfaces. Strict validation independently accepted queue state, archived
hashes, release structure, generated surfaces, and the exact provider pins.

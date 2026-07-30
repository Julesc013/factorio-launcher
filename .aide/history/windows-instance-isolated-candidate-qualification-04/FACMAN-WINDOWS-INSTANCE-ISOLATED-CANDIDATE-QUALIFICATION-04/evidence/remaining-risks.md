# Remaining risks

The producer, v3 contracts, and first diagnostic qualification remain
preserved. The reviewed stage-filename repair reached remote `dev`, and a
second fresh remote closure, clean build, qualification-04, and exact
revalidation-03 stage-only handoff all passed.

The principal residual risks are:

```text
repair integrated                 true
fresh repaired closure            pass
fresh repaired qualification      pass
revalidation-03 stage             staged_not_prepared
operator                           unassigned
prepare                            false
WPR/observer capture               false
Factorio execution                 false
human verdict                      unset
route authority                    false
```

The diagnostic closure and qualification roots are immutable evidence. They
must not be edited, renamed, cleaned, or passed to the repaired coordinator.
The accepted closure, qualification, and stage roots are also immutable and
must not be repaired in place.

Local validation also showed that `tools/dev.py verify-all` builds the default
CMake graph but does not explicitly request the three archive targets that
the promotion Python obligations require. The repair was validated by
building and binding those exact targets explicitly. Fixing the general
developer runner is a separate bounded test-infrastructure item and must not
be folded into this source-bound stage-handoff repair.

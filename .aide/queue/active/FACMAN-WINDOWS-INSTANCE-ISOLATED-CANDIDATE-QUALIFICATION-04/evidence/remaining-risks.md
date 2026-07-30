# Remaining risks

The producer, v3 contracts, remote source closure, and first qualification-04
all passed. That first qualification is diagnostic only because source review
found the coordinator would copy its v3 binding bytes to the historical v2
filename during stage.

The repair must reach reviewed remote `dev`. Then new empty roots must be used
for another remote source closure, clean build, and qualification-04. Only
that fresh repaired chain may be staged for revalidation-03.

The principal residual risks are:

```text
repair not yet integrated         true
fresh repaired closure            not started
fresh repaired qualification      not started
revalidation-03 stage             not started
prepare                            false
WPR/observer capture               false
Factorio execution                 false
human verdict                      unset
route authority                    false
```

The diagnostic closure and qualification roots are immutable evidence. They
must not be edited, renamed, cleaned, or passed to the repaired coordinator.

Local validation also showed that `tools/dev.py verify-all` builds the default
CMake graph but does not explicitly request the three archive targets that
the promotion Python obligations require. The repair was validated by
building and binding those exact targets explicitly. Fixing the general
developer runner is a separate bounded test-infrastructure item and must not
be folded into this source-bound stage-handoff repair.

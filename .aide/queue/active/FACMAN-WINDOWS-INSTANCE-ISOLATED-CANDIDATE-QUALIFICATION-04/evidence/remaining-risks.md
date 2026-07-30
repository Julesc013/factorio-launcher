# Remaining risks

The producer-binding source update is not itself qualification-04.

Before the WorkUnit can close, the reviewed change must reach remote `dev`,
then fresh empty-root remote source closure, a clean build, and a new
qualification report and digest must complete. Revalidation-03 must use those
new exact inputs.

Until then:

```text
producer binding integrated  false
remote source closure        not started
qualification generated      false
prepare                      false
Factorio execution           false
human verdict                unset
route authority              false
```

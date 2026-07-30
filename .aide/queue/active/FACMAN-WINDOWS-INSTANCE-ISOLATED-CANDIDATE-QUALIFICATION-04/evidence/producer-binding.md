# Qualification-04 producer binding

## Historical condition

The accepted producer was literally bound to:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-03
```

It therefore correctly refused a new qualification-04 task root. Running
qualification-04 without a reviewed source update would either fail or require
an unqualified ambient workaround.

## Bounded source update

The producer is now literally bound to:

```text
FACMAN-WINDOWS-INSTANCE-ISOLATED-CANDIDATE-QUALIFICATION-04
```

It continues to derive the task identity from the exact absolute task-root
name and refuses the historical qualification-03 root. No CLI or environment
override was introduced.

Qualification-04 emits new versioned bindings:

```text
qualification binding schema
facman.play_candidate_qualification_binding.v3

qualification report schema
facman.instance_isolated_candidate_qualification.v3

target evidence WorkUnit
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03
```

The accepted v2 schemas remain unchanged and continue to describe the
historical qualification-03/revalidation-02 chain.

The source update must reach reviewed remote `dev` before remote source
closure. Qualification evidence will not be generated from this local
worktree.

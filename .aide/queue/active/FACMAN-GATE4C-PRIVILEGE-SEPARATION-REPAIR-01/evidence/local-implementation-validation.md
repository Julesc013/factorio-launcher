# Gate 4C privilege-separation local implementation validation

Implementation revision:
`380c1a44f26cc1d6bacccdfe5ce0c6d2efda36d3`

Task-owned build root:

```text
E:\Temporary\FacMan\
  FACMAN-GATE4C-PRIVILEGE-SEPARATION-REPAIR-01\
    build\
```

No build tree or package output was created inside the source repository.

## Passing proof

```text
Windows MSVC Release native build                  PASS
Release CTest                                      PASS 50/50
Gate 4C focused native security tests              PASS 3/3
Non-package Python suite with external native CLI  PASS 411; 28 skipped
Package-runtime Python suite with external build   PASS 23; 2 skipped
Focused Gate 4C and truth Python tests              PASS 76; 2 skipped
Strict validators                                  PASS
Schema validation                                  PASS 286
Windows portable CLI package build                 PASS
Frozen policy digest                               unchanged
WPR after validation                               idle
Factorio processes                                 none
Gate 4C permits                                    none
Gate 4C baselines                                  none
Human verdict                                      unset
```

## Background UAC probe disposition

A no-WPR/no-Factorio privilege-boundary probe was attempted from the Codex
background tool channel. Windows did not expose the UAC consent UI to that
channel, so `ShellExecuteExW` remained at the consent boundary and no elevated
broker process appeared.

The exact task-owned waiting coordinator PID was terminated. Subsequent checks
confirmed:

```text
observer broker processes  none
Factorio processes         none
WPR                         not recording
probe evidence file        none
```

This is not a failed security result and is not counted as a passing live
probe. The committed probe must be run from the operator's normal interactive
desktop terminal and requires one UAC approval.

## Remaining local proof

```text
live medium coordinator -> high broker handshake
```

That probe starts neither WPR nor Factorio. Repair closeout and a fresh verdict
remain unavailable until its exact evidence is preserved and reviewed.

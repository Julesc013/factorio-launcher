# Gate 4C observer-start root cause

Date: 2026-07-24

## Bounded reproduction

The elevated diagnostic comparison ran the observer-start-only path directly
and through the real native process supervisor. Neither path issued a permit or
started Factorio. Both stopped before WPR startup with:

```text
gate4c-verdict-session: observer profile or provider identity is invalid
```

The two comparison records exist because two previously pending UAC requests
were approved. They are independent diagnostic-only repetitions of the same
failure, not product operations.

| Artifact | SHA-256 |
| --- | --- |
| `comparison-20260724t064229z-transcript.txt` | `c9cf5d29b68f628b6c1d989cdd8989c0e382c4bfeca299dd21e552039d43365d` |
| `comparison-20260724t064229z.json` | `05d04b117330211b49525d50d0b8eee2d3272f9fa69166b4fe5dbb91613c297b` |
| `gate4c-observer-start-probe-native-20260724t064229z-native-supervision.json` | `8edaef5882ed6ecdabc1cebc78e2d293e9e49e399a283e1cdf8c0e4be8bc6255` |
| `comparison-20260724t064308z-transcript.txt` | `87810df1f5cb547a91bcb6050c1fef41d748712f9391e18ec63ae0703e7e0887` |
| `comparison-20260724t064308z.json` | `5155139d8e665daa3f78a38e1a7be5e070237b852dfba12b257abcb454b3368d` |
| `gate4c-observer-start-probe-native-20260724t064308z-native-supervision.json` | `ca8e34bc06bfc35014115bf05064f9440e34644ad1dfcfffe1fc6ff72718f72c` |

The external artifacts remain under the exact task-owned root:

```text
E:\Temporary\FacMan\
  FACMAN-HERMETIC-STANDALONE-PLAY-OBSERVER-START-REPAIR-01\
    evidence\observer-start-probes\
```

## Root cause

`observer_profile_identity()` returned an explicit Boolean `valid` field.
`observer_provider_identity()` embedded the valid profile details but did not
return its own `valid` field.

Both the diagnostic observer-start boundary and the real session boundary used:

```python
not provider.get("valid")
```

The missing value therefore evaluated as invalid on every real observer start.
This refusal occurred before WPR, permit issuance, or process creation. It also
explains why the observer self-test could pass: the self-test checked the
profile and tool identities directly but did not require provider validity.

## Bounded correction

The correction:

1. propagates profile validity into the provider identity;
2. gives invalid provider identity an explicit reason;
3. advances the evidence schema and provider revision to v5 so prior v4
   self-test evidence cannot be reused;
4. makes the self-test require provider validity; and
5. exercises the real provider-identity constructor in the observer-start
   probe regression.

The frozen Gate 4A policy, Gate 4B candidate scope, permit core, public routes,
and Factorio execution behavior are unchanged.

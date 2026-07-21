# OperationPermit v1

`OperationPermit` is FacMan's internal, short-lived authority token for one
reviewed effect. Gate 3 establishes the contract and provider enforcement
mechanism. It does not expose product issuance and cannot launch Factorio.

## Boundary

The permit has two layers:

- `OperationPermitClaims` is the canonical immutable statement of one
  operation, one provider audience, exact effects and capabilities, exact
  resources, current evidence, policy, providers, machine, principal, time
  window, issuer session, and nonce.
- `OperationPermitEnvelope` authenticates the canonical claims digest with a
  process-session key. A schema-valid object, a bare claims object, or an
  unkeyed SHA-256 digest never grants authority.

Gate 3 uses `hmac-sha256.process.v1` behind a versioned authenticator
interface. The secret and complete envelope are never persisted, exported, or
written to ordinary logs. A future out-of-process provider may replace the
authenticator without changing claim semantics.

## Canonical law

Claims use `facman.sorted-json.v1`. Effects, capabilities, providers, and
resources are sorted before encoding. Duplicate effects, capabilities,
providers, or resource keys are refused. Resources are keyed by kind, role,
and logical ID and contain a current identity digest; paths and prefixes are
not resource identities, and wildcard authority is invalid.

The claims digest binds every claim. Resource input order cannot alter it, but
any semantic mutation must. `launch_intent` and `isolation_mode` are singular
nullable fields; when present, a different value requires a different permit.

## Time and restart law

Serialized times are UTC Unix seconds. The validator uses an injected wall
clock and the process-local ledger also records a monotonic deadline. Policy
sets a strict maximum lifetime and future-issuance tolerance. A permit is
invalid before `not_before`, at or after expiry, after its monotonic deadline,
or when the requested lifetime exceeds policy.

The issuer session and authentication key live only for the current process.
Application or provider restart loses them, so an old permit cannot be reused.
Recovery re-inspects current state and requires newly reviewed authority.

## Validation and consumption

Admission calls `validate`, which never consumes. The owning provider repeats
authentication, audience, operation, plan, policy, evidence, resource,
effect, capability, principal, machine, intent, isolation, time, and provider
checks against its own current observations. It then calls `consume`, which
atomically changes the nonce from issued to consumed immediately before the
effect. Sequential and concurrent replay are refused.

One envelope has one audience. Federated mutations require separately scoped
child permits; a bearer token is not shared across independent providers.

## Gate 3 non-authority guarantees

- There is no command or transport route that issues a permit.
- Read-only commands do not need a permit and remain non-authoritative.
- Fixture construction can exercise authentication but cannot reach a real
  process, Universal Setup, credentials, networking, signing, publication, or
  host mutation.
- The dormant Factorio launch verifier can validate and consume only; it has
  no process-launch dependency or execution entry point.
- `permit_issuance_authority` and real Factorio execution remain false until a
  later reviewed gate.

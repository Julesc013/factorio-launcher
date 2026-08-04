# Universal provider contract wave 01

Date: 2026-08-04

Universal Launcher and Universal Setup each completed one additive,
product-neutral provider WorkUnit from the exact ratified `dev` base. The
provider-local neutral fixtures qualify the new contracts only as
`fixture-qualified`.

| Provider | Task head | `dev` integration | synchronized `main`/`dev` |
| --- | --- | --- | --- |
| Universal Launcher | `766fe181709eaee15139303f95a649caf30abbda` | `9d79ae5e022c4366b890ce3cdee3d924863f2948` | `719a3ec240831547071d69098e1fe8c76f327fb7` |
| Universal Setup | `629d3011f784e833b26887a4b8403602c181a055` | `23b96f0da16eacd5ef26af9d0f331735558bf576` | `7f8f2baa14e78b0329db8eef8ac872818c4cf30d` |

ULK preserves the ABI 1.6 and 1.7 surfaces while adding the product,
entrypoint, capability, composition, and contract-set identity contracts.
USK adds strict product-package, component, local-source, setup-recipe, and
installed-state compatibility schemas without live mutation capability.

The exact task, `dev`, promotion-`main`, and promotion-`dev` hosted matrices
passed for both providers. FacMan's consumer locks remain
`7fc25340623131ba86c08dca4fb8a43b18a4520d` for ULK and
`3048128963dc718a7c38c1cfcdda9e813a23b0db` for USK. No consumer adoption,
product execution, setup mutation, signing, publication, or successor-route
authority is opened.

With both dependencies merged, `SYNTHETIC-PRODUCT-TCK-01` may now run as a
separate, development-only WorkUnit in the existing FacMan superbuild tests.
It must emit exact provider observations out of tree and must not change the
stable consumer locks.

# Validation

The original failure was reproduced before repair: the regression rejected
the missing `factorio_menu_observed` gate and the guest still used the
20-second close delay.

After repair:

```text
native release-route menu self-test       PASS (1/1)
route and Sandbox bundle tests            PASS (17/17)
route/security/CMake focused tests         PASS (28/28)
PowerShell parser                          PASS
schema validation                          PASS (365)
source format                              PASS
strict exact-provider validation           PASS
AIDE Lite                                  PASS
git diff whitespace                        PASS
```

The provisional final-source MSVC observer binary SHA-256 is
`334e9de394b8686927cf8256e372447ae2788289fa5e8566a4054251e17db356`.
It is not an execution permit and must be rebuilt after protected integration.

The exhausted two-launch evidence retained outside source is bound by:

```text
first launch receipt   84c3312da831ab7e71f1f839f3fb3f6aab01d21e0b37a055c05f1e6917942d6c
relaunch receipt       396fa60d120b8524f9110d6e53e0c255326647e487d9eb343d7066b54813396b
machine result         6c1f0673cfa4d9c9059f81c556fdbe4de23d4893cac84b9a668e4dbeb0ec9d02
execution plan         8c49669d3716aa04b34f04ed9e0b647ac5a13fb8b4f82107ce24cfd36def07f0
```

Both Factorio logs contain `Closed during loading.` and lack the exact
`Factorio initialised` marker. The machine route result is therefore Fail.

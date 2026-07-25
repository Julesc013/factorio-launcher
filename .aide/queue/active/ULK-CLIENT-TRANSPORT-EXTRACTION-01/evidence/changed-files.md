# Changed files

Universal Launcher provider revision `78c27da0de2cefc40ff0f9654ab46f777a1357ae`
adds the versioned `ulk_client_v1` and `ulk_transport_adapter_v1` ABI, direct,
process, and daemon transport kinds, the `ulk.client_transport.v1` contract,
and standalone native proof.

FacMan pins that provider revision, requires ULK ABI 1.4, routes its C binding
adapter through the neutral ULK client, removes the placeholder generic C
client and transport files, and preserves the FLB 1.x structured invalid
request response contract at the binding adapter.

Canonical project truth records the previous ULK revision as the immutable
historical Gate 4C candidate identity and requires candidate revalidation
against the new provider pin.

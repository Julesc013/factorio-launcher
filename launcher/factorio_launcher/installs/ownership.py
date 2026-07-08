MUTABLE_OWNERSHIPS = {"managed"}
READ_ONLY_OWNERSHIPS = {"foreign", "imported", "portable"}


def can_mutate_install(ownership: str) -> bool:
    return ownership in MUTABLE_OWNERSHIPS


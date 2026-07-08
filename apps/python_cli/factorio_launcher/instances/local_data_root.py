from pathlib import Path


def local_data_root(instance: dict[str, object]) -> Path:
    return Path(str(instance["local_data_root"]))


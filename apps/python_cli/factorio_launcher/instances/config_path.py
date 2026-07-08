from pathlib import Path


def config_ini(instance: dict[str, object]) -> Path:
    return Path(str(instance["local_data_root"])) / "config" / "config.ini"


def config_path_cfg(instance: dict[str, object]) -> Path:
    return Path(str(instance["local_data_root"])) / "config" / "config-path.cfg"


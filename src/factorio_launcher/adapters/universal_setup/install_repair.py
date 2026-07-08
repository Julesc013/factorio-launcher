from factorio_launcher.adapters.universal_setup.setup_client import require_setup_integration


def repair_install(install_id: str) -> None:
    require_setup_integration(f"repair install {install_id}")


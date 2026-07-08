from factorio_launcher.integrations.usk.setup_client import require_setup_integration


def repair_install(install_id: str) -> None:
    require_setup_integration(f"repair install {install_id}")

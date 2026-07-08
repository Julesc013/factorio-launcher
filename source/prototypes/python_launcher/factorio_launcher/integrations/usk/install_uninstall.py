from factorio_launcher.integrations.usk.setup_client import require_setup_integration


def uninstall_install(install_id: str) -> None:
    require_setup_integration(f"uninstall install {install_id}")

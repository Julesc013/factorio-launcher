from factorio_launcher.adapters.universal_setup.setup_client import require_setup_integration


def uninstall_install(install_id: str) -> None:
    require_setup_integration(f"uninstall install {install_id}")


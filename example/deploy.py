from pyinfra import inventory, state
from pyinfra_okd4 import (
    configure_firewall,
    copy_syslinux_files,
    create_directories,
    deploy_nginx_config,
    download_okd4_installer,
    enable_services,
    install_package_repos,
    install_packages,
)


# Run Deploys
install_package_repos()
install_packages()
create_directories()
copy_syslinux_files()
deploy_nginx_config()
configure_firewall()
enable_services()
download_okd4_installer()

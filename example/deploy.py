from pyinfra import inventory, state
from pyinfra_okd4 import (
    configure_firewall,
    copy_syslinux_files,
    create_directories,
    create_okd4_ignition_files,
    deploy_nginx_config,
    download_okd4_installer,
    download_fcos_pxe_images,
    enable_services,
    install_package_repos,
    install_packages,
    render_okd4_install_config,
    render_okd4_haproxy_cfg,
    render_okd4_dns_records,
    render_pxelinux_cfgs,
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

#kernel_image, initramfs_image, rootfs_image = download_fcos_pxe_images()
#render_pxelinux_cfgs()
#render_okd4_install_config()
#create_okd4_ignition_files()
#render_okd4_haproxy_cfg()
#render_okd4_dns_records()

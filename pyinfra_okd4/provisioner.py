import json
import requests

from os import path
from pyinfra import host
from pyinfra.api.deploy import deploy
from pyinfra.facts.files import Directory, File, FindInFile, Md5File, Sha256File
from pyinfra.facts.server import LinuxDistribution, Command, Which
from pyinfra.operations import files, server


# Handful of Helpers
def get_package_path(*paths):
    return path.join(path.dirname(__file__), *paths)


def get_files_path(filename):
    return get_package_path("files", filename)


def get_templates_path(filename):
    return get_package_path("templates", filename)


@deploy("Install Package Repositories")
def install_package_repos(state=None, host=None):
    if (
        host.get_fact(LinuxDistribution).get("name") == "CentOS"
        and host.get_fact(LinuxDistribution).get("major") <= 7
    ):
        # CentOS 7 or Earlier will need epel-release installed for nginx and haproxy
        server.packages(
            name="Install epel-release repo via package",
            packages=["epel-release"],
            state=state,
            host=host,
        )


@deploy("Install Packages")
def install_packages(state=None, host=None):
    # Install the necessary packages
    if host.get_fact(LinuxDistribution).get("name") in [
        "Fedora",
        "AlmaLinux",
        "CentOS",
    ]:
        server.packages(
            name="Install packages",
            packages=["tftp-server", "syslinux-tftpboot", "nginx", "haproxy"],
            state=state,
            host=host,
        )


@deploy("Create Directories")
def create_directories(state=None, host=None):
    # Create the directories we're going to need
    if host.get_fact(LinuxDistribution).get("name") in [
        "Fedora",
        "AlmaLinux",
        "CentOS",
    ]:

        # Create directories owned by the ssh_user
        okd_cluster_config_dir = (
            host.data.cluster_name + "." + host.data.cluster_domain + "-config"
        )
        user_dirs = [
            "bin",
            "Downloads",
            okd_cluster_config_dir,
        ]

        for user_dir in user_dirs:
            if not host.get_fact(Directory, user_dir):
                files.directory(
                    path=user_dir,
                    present=True,
                    user=host.data.ssh_user,
                    group=host.data.ssh_user,
                    mode="0700",
                    sudo=False,
                    state=state,
                    host=host,
                )

        # Create directories that need sudo
        sudo_dirs = [
            "/var/lib/tftpboot/images/fcos",
            "/var/lib/tftpboot/pxelinux.cfg",
            "/usr/share/nginx/html/fcos",
            "/usr/share/nginx/html/ignition",
        ]

        for sudo_dir in sudo_dirs:
            if not host.get_fact(Directory, sudo_dir):
                files.directory(
                    path=sudo_dir,
                    present=True,
                    user="root",
                    group="root",
                    mode="0755",
                    state=state,
                    host=host,
                )


@deploy("Copy Syslinux Files")
def copy_syslinux_files(state=None, host=None):
    # Copy the necessary syslinux files from the default install location to /var/lib/tftpboot
    if host.get_fact(LinuxDistribution).get("name") in ["Fedora", "AlmaLinux"]:
        for syslinux_file in [
            "ldlinux.c32",
            "libcom32.c32",
            "libutil.c32",
            "menu.c32",
            "pxelinux.0",
        ]:
            if host.get_fact(Md5File, f"/tftpboot/{syslinux_file}") != host.get_fact(
                Md5File, f"/var/lib/tftpboot/{syslinux_file}"
            ):
                server.shell(
                    name=f"Copy {syslinux_file} into place",
                    commands=[
                        f"cp /tftpboot/{syslinux_file} /var/lib/tftpboot/{syslinux_file}"
                    ],
                    state=state,
                    host=host,
                )


@deploy("Deploy NGINX Config")
def deploy_nginx_config(state=None, host=None):
    # Stomp the NGINX config if it doesn't have our locations
    if host.get_fact(LinuxDistribution).get("name") in [
        "Fedora",
        "AlmaLinux",
        "CentOS",
    ]:
        if not host.get_fact(FindInFile, "/etc/nginx/nginx.conf", "location /fcos/"):
            files.put(
                dest="/etc/nginx/nginx.conf",
                src=get_files_path("nginx.conf"),
                mode="0644",
                state=state,
                host=host,
            )
        if not host.get_fact(
            FindInFile, "/etc/nginx/nginx.conf", "location /ignition/"
        ):
            files.put(
                dest="/etc/nginx/nginx.conf",
                src=get_files_path("nginx.conf"),
                mode="0644",
                state=state,
                host=host,
            )


@deploy("Enable Services")
def enable_services(state=None, host=None):
    # Manage the Sevices
    if host.get_fact(LinuxDistribution).get("name") in [
        "Fedora",
        "AlmaLinux",
        "CentOS",
    ]:
        server.service(
            service="tftp.socket", running=True, enabled=True, state=state, host=host,
        )

        server.service(
            service="nginx.service", running=True, enabled=True, state=state, host=host,
        )


@deploy("Configure Firewall")
def configure_firewall(state=None, host=None):
    # Open the required firewall ports
    if host.get_fact(LinuxDistribution).get("name") in [
        "Fedora",
        "AlmaLinux",
        "CentOS",
    ]:
        active_services = host.get_fact(
            Command, "firewall-cmd --list-services", sudo=True
        )
        if "http" not in active_services:
            server.shell(
                commands="firewall-cmd --add-service=http", state=state, host=host
            )
            server.shell(
                commands="firewall-cmd --add-service=http --permanent",
                state=state,
                host=host,
            )
        if "https" not in active_services:
            server.shell(
                commands="firewall-cmd --add-service=https", state=state, host=host
            )
            server.shell(
                commands="firewall-cmd --add-service=https --permanent",
                state=state,
                host=host,
            )
        if "tftp" not in active_services:
            server.shell(
                commands="firewall-cmd --add-service=tftp", state=state, host=host
            )
            server.shell(
                commands="firewall-cmd --add-service=tftp --permanent",
                state=state,
                host=host,
            )


@deploy("Download OKD4 Installer")
def download_okd4_installer(state=None, host=None):

    # Download Latest OKD Installer
    #
    # Get the build tag or the latest release on GitHub
    release = requests.head("https://github.com/openshift/okd/releases/latest")

    latest_build_tag = release.headers.get("location").split("/")[-1]

    client_file = f"openshift-client-linux-{latest_build_tag}.tar.gz"
    install_file = f"openshift-install-linux-{latest_build_tag}.tar.gz"

    client_url = f"https://github.com/openshift/okd/releases/download/{latest_build_tag}/{client_file}"
    install_url = f"https://github.com/openshift/okd/releases/download/{latest_build_tag}/{install_file}"

    # Download the Latest OKD OpenShift Installer if it's not already on the path.
    for url in [client_url, install_url]:
        if not host.get_fact(File, f'Downloads/{url.split("/")[-1]}'):
            files.download(
                name=f'Downloading {url.split("/")[-1]}',
                src=url,
                dest=f'Downloads/{url.split("/")[-1]}',
                sudo=False,
                state=state,
                host=host,
            )

    # Extract the tar.gz files to ~/bin
    if not host.get_fact(File, "bin/openshift-install"):
        server.shell(
            commands=f"tar -xzf Downloads/{install_file} --directory bin",
            sudo=False,
            state=state,
            host=host,
        )

    if not host.get_fact(File, "bin/oc") and not host.get_fact(File, "bin/kubectl"):
        server.shell(
            commands=f"tar -xzf Downloads/{client_file} --directory bin",
            sudo=False,
            state=state,
            host=host,
        )


@deploy("Download FCOS PXE Images referenced in OKD Installer")
def download_fcos_pxe_images(state=None, host=None):

    # Parse the CoreOS stream metadata for the bootimages
    if host.get_fact(File, "bin/openshift-install"):
        coreos_stream_metadata = json.loads(
            host.get_fact(
                Command, "bin/openshift-install coreos print-stream-json", sudo=False
            )
        )
        pxe_metadata = (
            coreos_stream_metadata.get("architectures")
            .get("x86_64")
            .get("artifacts")
            .get("metal")
            .get("formats")
            .get("pxe")
        )
        kernel = pxe_metadata.get("kernel")
        initramfs = pxe_metadata.get("initramfs")
        rootfs = pxe_metadata.get("rootfs")

        # Parse out the filenames
        kernel_image = kernel.get("location").split("/")[-1]
        initramfs_image = initramfs.get("location").split("/")[-1]
        rootfs_image = rootfs.get("location").split("/")[-1]

        # Download the FCOS PXE Files that match this OKD Build
        if not host.get_fact(File, f"/var/lib/tftpboot/images/fcos/{kernel_image}"):
            files.download(
                name=f"Downloading {kernel_image}",
                src=kernel.get("location"),
                dest=f"/var/lib/tftpboot/images/fcos/{kernel_image}",
                sudo=True,
                state=state,
                host=host,
            )
        if not host.get_fact(File, f"/var/lib/tftpboot/images/fcos/{initramfs_image}"):
            files.download(
                name=f"Downloading {initramfs_image}",
                src=initramfs.get("location"),
                dest=f"/var/lib/tftpboot/images/fcos/{initramfs_image}",
                sudo=True,
                state=state,
                host=host,
            )
        if not host.get_fact(File, f"/user/share/nginx/html/fcos/{rootfs_image}"):
            files.download(
                name=f"Downloading {rootfs_image}",
                src=rootfs.get("location"),
                dest=f"/usr/share/nginx/html/fcos/{rootfs_image}",
                sudo=True,
                state=state,
                host=host,
            )

        return (kernel_image, initramfs_image, rootfs_image)


@deploy("Render pxelinux.cfg Files")
def render_pxelinux_cfgs(
    state=None, host=None, kernel_image=None, initramfs_image=None, rootfs_image=None
):
    # Render /var/lib/tftboot/pxelinux.cfg/~ files
    files.template(
        name="Render pxelinux.cfg/default file",
        src=get_templates_path("pxelinux.cfg/default.j2"),
        dest="/var/lib/tftpboot/pxelinux.cfg/default",
        mode="0644",
        user="root",
        group="root",
        kernel_image=kernel_image,
        initramfs_image=initramfs_image,
        rootfs_image=rootfs_image,
        state=state,
        host=host,
    )


@deploy("Render OKD4 install-config.yaml")
def render_okd4_install_config(state=None, host=None):
    # Render install-config.yaml
    ignition_dir = host.data.cluster_name + "." + host.data.cluster_domain + "-config"
    if not host.get_fact(File, f"{ignition_dir}-config/bootstrap.ign"):
        files.template(
            name="Render install-config.yaml file",
            src=get_templates_path("install-config.yaml.j2"),
            dest=f"{ignition_dir}/install-config.yaml",
            mode="0644",
            sudo=False,
            state=state,
            host=host,
        )


@deploy("Create OKD4 Cluster Ignition Files")
def create_okd4_ignition_files(state=None, host=None):
    # Run openshift-install to create Cluster Ignition files
    ignition_dir = host.data.cluster_name + "." + host.data.cluster_domain
    if host.get_fact(File, f"{ignition_dir}-config/install-config.yaml"):
        if not host.get_fact(File, f"{ignition_dir}-config/bootstrap.ign"):
            server.shell(
                name="Create OpenShift OKD Manifests",
                commands=f"bin/openshift-install create manifests --dir {ignition_dir}-config",
                sudo=False,
                state=state,
                host=host,
            )
            server.shell(
                name="Create OpenShift OKD Ignition Files",
                commands=f"bin/openshift-install create ignition-configs --dir {ignition_dir}-config",
                sudo=False,
                state=state,
                host=host,
            )

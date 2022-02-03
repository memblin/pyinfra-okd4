import json
import requests

from pyinfra import local, host
from pyinfra.api.deploy import deploy
from pyinfra.facts.server import LinuxDistribution, Command, Which
from pyinfra.facts.files import Directory, File, FindInFile, Md5File, Sha256File
from pyinfra.operations import files, server


# Download FCOS PXE Images mentions in OKD Installer
#
# Parse the CoreOS stream metadata for the bootimages
if host.get_fact(File, 'bin/openshift-install'):
    coreos_stream_metadata = json.loads(host.get_fact(Command, 'bin/openshift-install coreos print-stream-json', sudo = False))
    pxe_metadata = coreos_stream_metadata.get('architectures').get('x86_64').get('artifacts').get('metal').get('formats').get('pxe')
    kernel = pxe_metadata.get('kernel')
    initramfs = pxe_metadata.get('initramfs')
    rootfs = pxe_metadata.get('rootfs')

    # Parse out the filenames
    kernel_image = kernel.get('location').split('/')[-1]
    initramfs_image = initramfs.get('location').split('/')[-1]
    rootfs_image = rootfs.get('location').split('/')[-1]

    # Download the FCOS PXE Files that match this OKD Build
    if not host.get_fact(File, f'/var/lib/tftpboot/images/fcos/{kernel_image}'):
        files.download(
            name = f'Downloading {kernel_image}',
            src = kernel.get('location'),
            dest = f'/var/lib/tftpboot/images/fcos/{kernel_image}',
            sudo = True,
        )

    if not host.get_fact(File, f'/var/lib/tftpboot/images/fcos/{initramfs_image}'):
        files.download(
            name = f'Downloading {initramfs_image}',
            src = initramfs.get('location'),
            dest = f'/var/lib/tftpboot/images/fcos/{initramfs_image}',
            sudo = True,
        )

    if not host.get_fact(File, f'/user/share/nginx/html/fcos/{rootfs_image}'):
        files.download(
            name = f'Downloading {rootfs_image}',
            src = rootfs.get('location'),
            dest = f'/usr/share/nginx/html/fcos/{rootfs_image}',
            sudo = True,
        )

# Render /var/lib/tftboot/pxelinux.cfg/~ files
files.template(
        name = 'Render pxelinux.cfg/default file',
        src = 'templates/pxelinux.cfg/default.j2',
        dest = '/var/lib/tftpboot/pxelinux.cfg/default',
        mode = '0644',
        user = 'root',
        group = 'root',
        kernel_image = kernel_image,
        initramfs_image = initramfs_image,
        rootfs_image = rootfs_image,
    )

# Render install-config.yalm
ignition_dir = host.data.cluster_name + '.' + host.data.cluster_domain + '-config'
files.template(
        name = 'Render install-config.yaml file',
        src = 'templates/install-config.yaml.j2',
        dest = f'{ignition_dir}/install-config.yaml',
        mode = '0644',
        sudo = False,
    )

# Run openshift-install to create Cluster Ignition files
ignition_dir = host.data.cluster_name + '.' + host.data.cluster_domain
if host.get_fact(File, f'{ignition_dir}-config/install-config.yaml'):
    if not host.get_fact(File, f'{ignition_dir}-config/bootstrap.ign'):
        server.shell(
            name = 'Create OpenShift OKD Manifests',
            commands = f'bin/openshift-install create manifests --dir {ignition_dir}-config',
            sudo = False,
        )
        server.shell(
            name = 'Create OpenShift OKD Ignition Files',
            commands = f'bin/openshift-install create ignition-configs --dir {ignition_dir}-config',
            sudo = False,
        )



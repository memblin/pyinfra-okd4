import json
import requests

from pyinfra import local, host
from pyinfra.facts.server import LinuxDistribution, Command, Which
from pyinfra.facts.files import Directory, File, FindInFile, Md5File, Sha256File
from pyinfra.operations import files, server

distro = host.get_fact(LinuxDistribution)

# CentOS 7 or Earlier will need epel-release installed for nginx
if distro.get('name') == 'CentOS' and distro.get('major') <= 7:
    server.packages(
            name = 'Install epel-release repo',
            packages = ['epel-release'],
    )

# Install the necessary packages
if distro.get('name') in ['Fedora','AlmaLinux','CentOS']:
    server.packages(
            name = 'Install required packages',
            packages = ['tftp-server','syslinux-tftpboot','nginx','haproxy'],
    )

# Create the necessary directories
if distro.get('name') in ['Fedora','AlmaLinux','CentOS']:

    # Create directories owned by the ssh_user
    okd_cluster_config_dir = host.data.cluster_name + '.' + host.data.cluster_domain + '-config'
    user_dirs = [
            'bin',
            'Downloads',
            okd_cluster_config_dir,
    ]
    for user_dir in user_dirs:
        if not host.get_fact(Directory, user_dir):
            files.directory(
                    path = user_dir,
                    present = True,
                    user = host.data.ssh_user,
                    group = host.data.ssh_user,
                    mode = '0700',
                    sudo = False,
            )

    # Create directories that need sudo
    sudo_dirs = [
            '/var/lib/tftpboot/images/fcos',
            '/var/lib/tftpboot/pxelinux.cfg',
            '/usr/share/nginx/html/fcos',
            '/usr/share/nginx/html/ignition',
    ]
    for sudo_dir in sudo_dirs:
        if not host.get_fact(Directory, sudo_dir):
            files.directory(
                    path = sudo_dir,
                    present = True,
                    user = 'root',
                    group = 'root',
                    mode = '0755',
            )

# Copy the necessary syslinux files from the default install location to /var/lib/tftpboot
if distro.get('name') in ['Fedora','AlmaLinux']:
    for syslinux_file in ['ldlinux.c32','libcom32.c32','libutil.c32','menu.c32','pxelinux.0']:
        if host.get_fact(Md5File, f'/tftpboot/{syslinux_file}') != host.get_fact(Md5File, f'/var/lib/tftpboot/{syslinux_file}'):
            server.shell(
                    name = f'Copy {syslinux_file} into place',
                    commands = [f'cp /tftpboot/{syslinux_file} /var/lib/tftpboot/{syslinux_file}'],
            )

# Stomp the NGINX config if it doesn't have our locations
if distro.get('name') in ['Fedora','AlmaLinux','CentOS']:
    if not host.get_fact(FindInFile, '/etc/nginx/nginx.conf', 'location /fcos/'):
            files.put(dest='/etc/nginx/nginx.conf', src='files/nginx.conf', mode='0644',)
    if not host.get_fact(FindInFile, '/etc/nginx/nginx.conf', 'location /ignition/'):
            files.put(dest='/etc/nginx/nginx.conf', src='files/nginx.conf', mode='0644',)

# Manage the Sevices
if distro.get('name') in ['Fedora','AlmaLinux','CentOS']:
    if  host.get_fact(Command, 'systemctl is-active tftp.socket', sudo = True) != 'active':
        server.service(
                service = 'tftp.socket',
                running = True,
                enabled = True,
        )

    if host.get_fact(Command, 'systemctl is-active nginx.service', sudo = True) != 'active':
        server.service(
                service = 'nginx.service',
                running = True,
                enabled = True,
        )

# Open the required firewall ports
if distro.get('name') in ['Fedora','AlmaLinux','CentOS']:

    active_services = host.get_fact(Command, 'firewall-cmd --list-services', sudo = True)

    if 'http' not in active_services:
        server.shell(commands='firewall-cmd --add-service=http')
        server.shell(commands='firewall-cmd --add-service=http --permanent')
    if 'https' not in active_services:
        server.shell(commands='firewall-cmd --add-service=https')
        server.shell(commands='firewall-cmd --add-service=https --permanent')
    if 'tftp' not in active_services:
        server.shell(commands='firewall-cmd --add-service=tftp')
        server.shell(commands='firewall-cmd --add-service=tftp --permanent')

# Download Latest OKD Installer
#
# Get the build tag or the latest release on GitHub
release = requests.head('https://github.com/openshift/okd/releases/latest')

latest_build_tag = release.headers.get('location').split('/')[-1]

client_file = f'openshift-client-linux-{latest_build_tag}.tar.gz'
install_file = f'openshift-install-linux-{latest_build_tag}.tar.gz'

client_url = f'https://github.com/openshift/okd/releases/download/{latest_build_tag}/{client_file}'
install_url = f'https://github.com/openshift/okd/releases/download/{latest_build_tag}/{install_file}'

# Download the Latest OKD OpenShift Installer if it's not already on the path.
for url in [client_url, install_url]:
    if not host.get_fact(File, f'Downloads/{url.split("/")[-1]}'):
        files.download(
                name = f'Downloading {url.split("/")[-1]}',
                src = url,
                dest = f'Downloads/{url.split("/")[-1]}',
                sudo = False,
    )

# Extract the tar.gz files to ~/bin
if not host.get_fact(File, 'bin/openshift-install'):
    server.shell(commands=f'tar -xzf Downloads/{install_file} --directory bin', sudo = False)

if not host.get_fact(File, 'bin/oc') and not host.get_fact(File, 'bin/kubectl'):
    server.shell(commands=f'tar -xzf Downloads/{client_file} --directory bin', sudo = False)

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



from pyinfra import inventory, state

from pyinfra_okd4 import (
    get_repos(),
    make_directories(),
)

SUDO = True
FAIL_PERCENT = 0

# Run Deploys
get_repos()
make_directories()

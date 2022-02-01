# pyinfra-okd4
Configure OKD4 Installation Utility / PXE Helper

- Install pyinfra, I use a conda env or py3 venv

- Copy `group_data/all.py.example` to `group_data/all.py` and adjust the values

- Deploy will not coplete without a valid SSH key and PullSecret in `group_data/all.py` but you shouldn't commit your pull secret to the repo

- Update `inventories.py` to point at the host you want to configure.
  - I imagnie normal use-cases this would be a single node, the repo has 3 because I'm testing against CentOS7, Alma8, and Fedora


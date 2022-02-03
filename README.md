# pyinfra-okd4

## Configure [OKD4](https://www.okd.io/) Provisioning Server using [pyinfra](https://pyinfra.com/).

A [User Provisioned Baremetal Install via PXE Boot for OKD4](https://docs.okd.io/latest/installing/installing_bare_metal/installing-bare-metal.html) requires
TFTP, HTTP, and Load Balancer services be configured and available

This module contains deploys to configure the required services on a standalone provisioning server allowing deployment of PXE booted Ignition configured OKD4 clusters.

## Usage

- Not ready for use yet, still a work in progress

- Deploy will not complete without a valid SSH key and PullSecret in `group_data/all.py` but you shouldn't commit your pull secret to the repo


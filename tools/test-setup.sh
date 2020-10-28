#!/bin/bash
set -euxo pipefail
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

export ANSIBLE_STDOOUT_CALLBACK=yaml

# bindep does only install epel-release fron centos-8, so we need to help it
which ansible-playbook || {
  sudo dnf install -y ansible
}

ansible-playbook -v "${DIR}/../playbooks/test-setup.yaml"

# Used to test that Vagrant is usable and also to pre-download the image
# we will use during testing.
cd "$DIR"

# sudo su: dirty hack to make sure that usermod change has been taken into account
# sudo su -l "$(whoami)" -c "cd $(pwd) && timeout 300 vagrant up --no-tty --no-provision --debug"
# sudo su -l "$(whoami)" -c "cd $(pwd) && vagrant destroy -f"
timeout 300 vagrant up --no-tty --no-provision --debug
vagrant destroy -f

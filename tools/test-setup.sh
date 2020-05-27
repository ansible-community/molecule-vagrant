#!/bin/bash
set -euxo pipefail
# Used by Zuul CI to perform extra bootstrapping

# Platforms coverage:
# Fedora 30 : has vagrant-libvirt no compilation needed
# CentOS 7  : install upstream vagrant rpm and compiles plugin (broken runtime)
# CentOS 8  : install upstream vagrant rpm and compiles plugin (broken runtime)

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Bumping system tox because version from CentOS 7 is too old
# We are not using pip --user due to few bugs in tox role which does not allow
# us to override how is called. Once these are addressed we will switch back
# non-sudo
command -v python3 python

PYTHON=$(command -v python3 python|head -n1)
PKG_CMD=$(command -v dnf yum|head -n1)

sudo $PYTHON -m pip install -U tox "zipp<0.6.0;python_version=='2.7'"

# === LIBVIRT SETUP ===
# https://bugs.launchpad.net/ubuntu/+source/libvirt/+bug/1588004
sudo rm -f /etc/systemd/libvirtd.service /etc/systemd/system/multi-user.target.wants/libvirt-bin.service || true
sudo systemctl enable --now libvirtd
sudo usermod --append --groups libvirt "$(whoami)"

# === VAGRANT SETUP ===
# Install Vagrant using their questionable practices, see locked ticket:
# https://github.com/hashicorp/vagrant/issues/11070

which vagrant || \
    sudo $PKG_CMD install -y vagrant-libvirt || {
        sudo $PKG_CMD install -y https://releases.hashicorp.com/vagrant/2.2.7/vagrant_2.2.7_x86_64.rpm
    }

# https://bugzilla.redhat.com/show_bug.cgi?id=1839651
if [ -f /etc/fedora-release ]; then
    grep -qi '^fedora.*31' /etc/fedora-release
    if [ $? -eq 0 ]; then
        sudo $PKG_CMD upgrade -y --enablerepo=updates-testing --advisory=FEDORA-2020-09c472786c
    fi
fi

vagrant plugin list | grep vagrant-libvirt || {
    export CONFIGURE_ARGS="with-libvirt-include=/usr/include/libvirt with-libvirt-lib=/usr/lib64"
    if [ -x /opt/vagrant/bin/vagrant ]; then
        # command line from https://github.com/vagrant-libvirt/vagrant-libvirt#installation
        export GEM_HOME=~/.vagrant.d/gems
        export GEM_PATH=$GEM_HOME:/opt/vagrant/embedded/gems
        export PATH=/opt/vagrant/embedded/bin:$PATH
        export CONFIGURE_ARGS='with-ldflags=-L/opt/vagrant/embedded/lib with-libvirt-include=/usr/include/libvirt with-libvirt-lib=/usr/lib'
    fi
    vagrant plugin install vagrant-libvirt
}

rpm -qa | grep libselinux

vagrant version
vagrant global-status

vagrant plugin list | tee >(grep -q "No plugins installed." && {
    echo "FATAL: Vagrant is not usable without any provider plugins."
    exit 1
})

# Used to test that Vagrant is usable and also to pre-download the image
# we will use during testing.
cd $DIR

vagrant up --no-provision
vagrant destroy -f

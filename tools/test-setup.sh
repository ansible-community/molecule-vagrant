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
PKG_CMD=$(command -v dnf yum apt-get|head -n1)

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
        sudo $PKG_CMD install -y https://releases.hashicorp.com/vagrant/2.2.9/vagrant_2.2.9_x86_64.rpm
    }

# https://bugzilla.redhat.com/show_bug.cgi?id=1839651
if [ -f /etc/fedora-release ]; then
    grep -qi '^fedora.*31' /etc/fedora-release
    if [ $? -eq 0 ]; then
        sudo $PKG_CMD upgrade -y --enablerepo=updates-testing --advisory=FEDORA-2020-09c472786c
    fi
fi

# https://github.com/hashicorp/vagrant/issues/11020
if [ -f /etc/centos-release ]; then
    grep -qi '^CentOS Linux release 8.2.*' /etc/centos-release
    if [ $? -eq 0 ]; then
        # https://bugs.centos.org/view.php?id=17120
        relver="$(cat /etc/centos-release | awk '{print $4}')"
        sudo sed -i /etc/yum.repos.d/CentOS-Sources.repo -e 's,$contentdir/,,g'
        sudo sed -i /etc/yum.repos.d/CentOS-Sources.repo -e "s,\$releasever,$relver,g"
        # Should avoid the "error: [Errno 13] Permission denied: '/var/cache/dnf/expired_repos.json'"
        sudo dnf makecache

        sudo dnf install -y rpm-build autoconf libselinux-devel pam-devel bison byacc
        mkdir -p rpmbuild/SOURCES
        cd rpmbuild/SOURCES
        sudo dnf download --enablerepo=BaseOS-source --disablerepo=epel-source --disablerepo=epel --source krb5-libs
        rpm2cpio krb5-1.17-*.src.rpm | cpio -id
        # remove patch making incompatible with the openssl bundled with vagrant
        sed -i ./krb5.spec -e 's,Patch.*Use-backported-version-of-OpenSSL-3-KDF-interface.patch,,'
        # depends on previous patch
        sed -i ./krb5.spec -e 's,Patch.*krb5-1.17post2-DES-3DES-fixups.patch,,'
        # not sure why but makes the build fail
        sed -i ./krb5.spec -e 's,Patch.*krb5-1.17post6-FIPS-with-PRNG-and-RADIUS-and-MD4.patch,,'
        rpmbuild -bp krb5.spec --nodeps
        cd ../BUILD/krb5-1.17/src
        # Some flags are missing compared to the spec but these ones seem to be enough
        export CFLAGS="-I/opt/vagrant/embedded/include/ -fPIC -fno-strict-aliasing -fstack-protector-all"
        export LDFLAGS=-L/opt/vagrant/embedded/lib64/
        ./configure --prefix=/opt/vagrant/embedded/
        make
        sudo cp -a lib/crypto/libk5crypto.so.3* /opt/vagrant/embedded/lib64/
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

if [ -f /etc/debian_version ]; then
    dpkg -l | grep libselinux
    [ -x /usr/bin/aa-enabled ] && echo "Apparmor: `/usr/bin/aa-enabled`"
else
    rpm -qa | grep libselinux
fi

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

#!/bin/bash
set -euxo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Used to test that Vagrant is usable and also to pre-download the image
# we will use during testing.
cd $DIR

vagrant box list |grep -qw testbox && exit 0

rm -f testbox.box
vagrant up --no-tty --debug
vagrant halt
vagrant package --output testbox.box
vagrant box add testbox.box --name testbox
vagrant destroy -f

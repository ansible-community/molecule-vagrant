***********************
Molecule Vagrant Plugin
***********************

.. image:: https://badge.fury.io/py/molecule-vagrant.svg
   :target: https://badge.fury.io/py/molecule-vagrant
   :alt: PyPI Package

.. image:: https://zuul-ci.org/gated.svg
   :target: https://dashboard.zuul.ansible.com/t/ansible/builds?project=ansible-community/molecule-vagrant

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/python/black
   :alt: Python Black Code Style

.. image:: https://img.shields.io/badge/Code%20of%20Conduct-silver.svg
   :target: https://docs.ansible.com/ansible/latest/community/code_of_conduct.html
   :alt: Ansible Code of Conduct

.. image:: https://img.shields.io/badge/Mailing%20lists-silver.svg
   :target: https://docs.ansible.com/ansible/latest/community/communication.html#mailing-list-information
   :alt: Ansible mailing lists

.. image:: https://img.shields.io/badge/license-MIT-brightgreen.svg
   :target: LICENSE
   :alt: Repository License

Molecule Vagrant is designed to allow use of Vagrant for provisioning of test
resources.

Supported Platforms
===================

This driver relies on vagrant command line which is known to be problematic
to install on several platforms. We do our best to perform CI/CD testing on
multiple platforms but some are disabled due to known bugs.

* ✅ MacOS with VirtualBox - GitHub Actions
* ✅ Fedora 32 with libvirt - Zuul
* ✅ Ubuntu Bionic (18.04) with libvirt - Zuul
* ❌ CentOS 8 with libvirt - Zuul DISABLED due to 1127_ and 11020_

Please **do not file bugs for unsupported platforms**. You are welcomed to
create PRs that fix untested platform, as long they do not break existing ones.

.. _`1127`: https://github.com/vagrant-libvirt/vagrant-libvirt/issues/1127
.. _`11020`: https://github.com/hashicorp/vagrant/issues/11020


Examples
========

To use this plugin, you'll need to set the ``driver`` and ``platform``
variables in your ``molecule.yml``. Here's a simple example using the
`fedora/32-cloud-base`_ box:

.. code-block:: yaml

   driver:
     name: vagrant

   platforms:
     - name: instance
       box: fedora/32-cloud-base
       memory: 512
       cpus: 1

Here's a full example with the libvirt provider:

.. code-block:: yaml

   driver:
     name: vagrant
     provider:
       # Can be any supported provider (virtualbox, parallels, libvirt, etc)
       # Defaults to virtualbox
       name: libvirt
     # Run vagrant up with --provision.
     # Defaults to --no-provision)
     provision: no
     # vagrant-cachier configuration
     # Defaults to 'machine'
     # Any value different from 'machine' or 'box' will disable it
     cachier: machine
     # If set to false, set VAGRANT_NO_PARALLEL to '1'
     # Defaults to true
     parallel: true
     # vagrant box to use by default
     # Defaults to 'generic/alpine310'
     default_box: 'generic/alpine310'

   platforms:
     - name: instance
       # List of dictionaries mapped to `config.vm.network`
       interfaces:
         # `network_name` is the required identifier, all other keys map to
         # arguments.
         - auto_config: true
           network_name: private_network
           type: dhcp
         - network_name: private_network
           ip: 192.168.123.3
         - network_name: forwarded_port
           guest: 80
           host: 8080
       # List of raw Vagrant `config` options
       instance_raw_config_args:
         # use single quotes to avoid YAML parsing as dict due to ':'
         - 'vm.synced_folder ".", "/vagrant", type: "rsync"'
         # Run 'uname' a provisionning step **needs 'provision: true' to work**
         - 'vm.provision :shell, inline: "uname"'
       # Dictionary of `config` options. Note that string values need to be
       # explicitly enclosed in quotes.
       config_options:
         ssh.keep_alive: yes
         ssh.remote_user: 'vagrant'
         synced_folder: true
       box: fedora/32-cloud-base
       box_version: 32.20200422.0
       box_url:
       memory: 512
       cpus: 1
       # Dictionary of options passed to the provider
       provider_options:
         video_type: 'vga'
       # List of raw provider options
       provider_raw_config_args:
         - cpuset = '1-4,^3,6'

.. _`fedora/32-cloud-base`: https://app.vagrantup.com/fedora/boxes/32-cloud-base


More examples may be found in the ``molecule`` `scenarios directory`_.
They're the scenarios used by the CI.


Instance definition
===================

Instances are defined with the ``platforms`` list. Each member of this list
is a dictionary defining the instance parameters, which will be used to
write a ``Vagrantfile``.

Simple options
--------------

Most of the options are mapping directly to the ``Vagrantfile`` configuration
line and have intuitive names:

- ``name``: name of the instance
- ``memory``: memory in MB (defaults to 512MB)
- ``cpus``: number of vcpus (defaults to 2)
- ``box``, ``box_version``, ``box_url``, ``box_download_checksum``,
  ``box_download_checksum_type``: definition of the box to use.
  They directly map to the option of the same name in ``config.vm``
- ``hostname``: host name of the machine. By default, use the instance name.

For more details, see `machine settings`_

.. _`machine settings`: https://www.vagrantup.com/docs/vagrantfile/machine_settings



Configuration options
---------------------

The parameters defined with the ``config_options`` key are configuration
options not already handled in previous section. If the option is complex,
``instance_raw_config_args`` may be used for that.

*Please note that the option names have to be defined with their namespace*.

One more thing to note is that ``config_options['synced_folder']`` has a
special meaning. It's not a configuration option of Vagrant. It's only enabling
or not the `synced folder`_ feature of Vagrant. It does not allow to configure
this feature. To configure it, the easiest way is to use
``instance_raw_config_args``.


In order to define `config.vm.allow_hosts_modification`_ and
`config.ssh.remote_user`_, the following definition will be used:

.. code-block:: yaml

   platforms:
     - name: instance
       config_options:
         ssh.remote_user: 'vagrant'
         vm.allow_hosts_modification: false


A more complex example, with:

- an inline shell script for `config.vm.provision`_,
- `synced folder`_ enabled and configured.


.. code-block:: yaml

   platforms:
     - name: myinstance
       provision: true
       config_options:
         synced_folder: true
       instance_raw_config_args:
         - "vm.provision :shell, inline: \"echo hello\""
         - 'vm.synced_folder ".", "/vagrant", type: "rsync"'


These examples will translate into the following ``Vagrantfile``:

.. code-block:: ruby

    Vagrant.configure('2') do |config|
      ...
      config.vm.define "myinstance" do |c|
        ...
        c.ssh.remote_user: "vagrant"
        c.vm.allow_hosts_modification: false
        ...
        c.vm.provision :shell, inline: "echo hello"
        c.vm.synced_folder ".", "/vagrant", type: "rsync"
        ...
      end
    end


.. _`synced folder`: https://www.vagrantup.com/docs/synced-folders/basic_usage
.. _`config.vm.allow_hosts_modification`: https://www.vagrantup.com/docs/vagrantfile/machine_settings#config-vm-allow_hosts_modification
.. _`config.ssh.remote_user`: https://www.vagrantup.com/docs/vagrantfile/ssh_settings#config-ssh-remote_user
.. _`config.vm.provision`: https://www.vagrantup.com/docs/vagrantfile/machine_settings#config-vm-provision


Provider options
----------------

The parameters defined with the ``provider_options`` key are options used to
configure the provider. As for ``config_options``, there's a
``provider_raw_config_args`` key for complex values. Additionally, it's
possible to configure `provider overrides`_ with ``provider_override_args``.


Example of provider options for vagrant-libvirt (`Reference vagrant-libvirt`_):

.. code-block:: yaml

   platforms:
     - name: myinstance
       provider_options:
         qemu_use_session: false
       provider_raw_config_args:
         - "storage :file, :type => 'qcow2', :device => 'vdb', :size => '1G'"


Resulting ``Vagrantfile``:

.. code-block:: ruby

    Vagrant.configure('2') do |config|
      ...
      config.vm.define "myinstance" do |c|
        ...
        c.vm.provider "libvirt" do |libvirt, override|
          ...
          libvirt.qemu_use_session: false
          libvirt.storage :file, :type => 'qcow2', :device => 'vdb', :size => '20G'
          ...
        end
        ...
      end
    end

Example of provider options for virtualbox
(`Reference virtualbox configuration`_, `Reference virtualbox customizations`_):

.. code-block:: yaml

   platforms:
     - name: myinstance
       provider_options:
         default_nic_type: 82543GC
       provider_raw_config_args:
         - "customize ['createmedium', 'disk', '--filename', 'machine1_disk0', '--size', '8196']"
         - "customize ['createmedium', 'disk', '--filename', 'machine1_disk1', '--size', '8196']"
         - "customize ['storageattach', :id, '--storagectl', 'SATA Controller','--port', '1', '--type', 'hdd', '--medium', 'machine1_disk0.vdi']"
         - "customize ['storageattach', :id, '--storagectl', 'SATA Controller','--port', '2', '--type', 'hdd', '--medium', 'machine1_disk1.vdi']"


Resulting ``Vagrantfile``:

.. code-block:: ruby

    Vagrant.configure('2') do |config|
      ...
      config.vm.define "myinstance" do |c|
        ...
        c.vm.provider "virtualbox" do |virtualbox, override|
          ...
          virtualbox.default_nic_type = "82543GC"
          virtualbox.customize ['createmedium', 'disk', '--filename', 'machine1_disk0', '--size', '8196']
          virtualbox.customize ['createmedium', 'disk', '--filename', 'machine1_disk1', '--size', '8196']
          virtualbox.customize ['storageattach', :id, '--storagectl', 'SATA Controller','--port', '1', '--type', 'hdd', '--medium', 'machine1_disk0.vdi']
          virtualbox.customize ['storageattach', :id, '--storagectl', 'SATA Controller','--port', '2', '--type', 'hdd', '--medium', 'machine1_disk1.vdi']
          ...
        end
        ...
      end
    end

The two disk examples are taken from `bug 127`_ .

Example of override:

.. code-block:: yaml

   platforms:
     - name: myinstance
       box: fedora/32-cloud-base
       provider_override_args:
         - 'vm.box = "bionic64"'


Resulting ``Vagrantfile``:

.. code-block:: ruby

    Vagrant.configure('2') do |config|
      ...
      config.vm.define "myinstance" do |c|
        ...
        c.vm.box = "fedora/32-cloud-base"
        ...
        c.vm.provider "virtualbox" do |virtualbox, override|
          ...
          override.vm.box = "bionic64"
          ...
        end
        ...
      end
    end



.. _`provider overrides`: https://www.vagrantup.com/docs/providers/configuration#overriding-configuration
.. _`Reference vagrant-libvirt`: https://github.com/vagrant-libvirt/vagrant-libvirt
.. _`Reference virtualbox configuration`: https://www.vagrantup.com/docs/providers/virtualbox/configuration#default-nic-type
.. _`Reference virtualbox customizations`: https://www.vagrantup.com/docs/providers/virtualbox/configuration#vboxmanage-customizations
.. _`bug 127`: https://github.com/ansible-community/molecule-vagrant/issues/127

Specific provider notes
-----------------------

While molecule-vagrant tries to be as generic as possible, there are things
to take into account:

- If the `linked_clone`_ is not set in ``provider_options`` for the virtualbox
  provider, it will defaults to true.
- When using vagrant-libvirt, if either ``/dev/kvm`` does not exists or
  ``provider_options['driver']`` is set to ``qemu``, it will set the cpu model
  to ``qemu64`` to workaround troubles with ``ssh-keygen`` on some OS. It can
  be overridden either by setting ``provider_options['driver']`` not to
  ``qemu`` or by setting ``provider_options['cpu_mode']`` and
  ``provider_options['cpu_model']``.


.. _`linked_clone`: https://www.vagrantup.com/docs/providers/virtualbox/configuration#linked-clones

Networking
----------

The networking of the instance is defined with the ``interfaces`` key. It's
content is a list defining the network name/type with ``network_name`` and its
options.

For instance (See `vagrant networking`_ for details):

.. code-block:: yaml

    interfaces:
      - network_name: private_network
        auto_config: true
        type: dhcp
      - network_name: private_network
        ip: 192.168.123.3
      - network_name: forwarded_port
        guest: 80
        host: 8080

gives:

.. code-block:: ruby

   c.vm.network "private_network", auto_config: true, type: "dhcp"
   c.vm.network "private_network", ip: "192.168.123.3"
   c.vm.network "forwarded_port", guest: 80, host: 8080

.. _`vagrant networking`: https://www.vagrantup.com/docs/networking


.. _get-involved:

Get Involved
============

* Join us in the ``#ansible-devtools`` channel on `Libera`_.
* Join the discussion in `molecule-users Forum`_.
* Join the community working group by checking the `wiki`_.
* Want to know about releases, subscribe to `ansible-announce list`_.
* For the full list of Ansible email Lists, IRC channels see the
  `communication page`_.

.. _`Libera`: https://web.libera.chat/?channel=#ansible-devtools
.. _`molecule-users Forum`: https://groups.google.com/forum/#!forum/molecule-users
.. _`wiki`: https://github.com/ansible/community/wiki/Molecule
.. _`ansible-announce list`: https://groups.google.com/group/ansible-announce
.. _`communication page`: https://docs.ansible.com/ansible/latest/community/communication.html
.. _`scenarios directory`: https://github.com/ansible-community/molecule-vagrant/tree/main/molecule_vagrant/test/scenarios/molecule
.. _authors:

Authors
=======

Molecule Vagrant Plugin was created by Sorin Sbarnea based on code from
Molecule.

.. _license:

License
=======

The `MIT`_ License.

.. _`MIT`: https://github.com/ansible-community/molecule-vagrant/blob/main/LICENSE

The logo is licensed under the `Creative Commons NoDerivatives 4.0 License`_.

If you have some other use in mind, contact us.

.. _`Creative Commons NoDerivatives 4.0 License`: https://creativecommons.org/licenses/by-nd/4.0/

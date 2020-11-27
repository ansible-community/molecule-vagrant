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


Documentation
=============

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
       # Can be any supported provider (VBox, Parallels, libvirt, etc)
       name: libvirt

   platforms:
     - name: instance
       # List of dictionaries mapped to `config.vm.network`
       interfaces:
         # `network_name` is the required identifier, all other keys map to
         # arguments.
         - network_name: forwarded_port
           guest: 80
           host: 8080
       # List of raw Vagrant `config` options
       instance_raw_config_args:
         - 'vagrant.plugins = ["vagrant-libvirt"]'
       # Dictionary of `config` options. Note that string values need to be
       # explicitly enclosed in quotes.
       config_options:
         ssh.keep_alive: yes
         ssh.remote_user: "'vagrant'"
       box: fedora/32-cloud-base
       box_version: 32.20200422.0
       box_url:
       memory: 512
       cpus: 1
       # Dictionary of options passed to the provider
       provider_options:
         video_type: "'vga'"
       # List of raw provider options
       provider_raw_config_args:
         - "cpuset = '1-4,^3,6'"
       provision: no

.. _`fedora/32-cloud-base`: https://app.vagrantup.com/fedora/boxes/32-cloud-base

.. _get-involved:

Get Involved
============

* Join us in the ``#ansible-molecule`` channel on `Freenode`_.
* Join the discussion in `molecule-users Forum`_.
* Join the community working group by checking the `wiki`_.
* Want to know about releases, subscribe to `ansible-announce list`_.
* For the full list of Ansible email Lists, IRC channels see the
  `communication page`_.

.. _`Freenode`: https://freenode.net
.. _`molecule-users Forum`: https://groups.google.com/forum/#!forum/molecule-users
.. _`wiki`: https://github.com/ansible/community/wiki/Molecule
.. _`ansible-announce list`: https://groups.google.com/group/ansible-announce
.. _`communication page`: https://docs.ansible.com/ansible/latest/community/communication.html

.. _authors:

Authors
=======

Molecule Vagrant Plugin was created by Sorin Sbarnea based on code from
Molecule.

.. _license:

License
=======

The `MIT`_ License.

.. _`MIT`: https://github.com/ansible/molecule/blob/master/LICENSE

The logo is licensed under the `Creative Commons NoDerivatives 4.0 License`_.

If you have some other use in mind, contact us.

.. _`Creative Commons NoDerivatives 4.0 License`: https://creativecommons.org/licenses/by-nd/4.0/

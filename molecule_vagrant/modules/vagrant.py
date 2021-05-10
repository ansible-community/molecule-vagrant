#!/usr/bin/python
# -*- coding: utf-8 -*-

#  Copyright (c) 2015-2018 Cisco Systems, Inc.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.


from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
import contextlib
import datetime
import io
import os
import subprocess
import sys

import molecule
import molecule.util

try:
    import vagrant
except ImportError:
    sys.exit("ERROR: Driver missing, install python-vagrant.")
ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = """
---
module: vagrant
short_description: Manage Vagrant instances
description:
  - Manage the life cycle of Vagrant instances.
  - Supports check mode. Run with --check and --diff to view config difference,
    and list of actions to be taken.
version_added: 2.0
author:
  - Cisco Systems, Inc.
options:
  instance_name:
    description:
      - Assign a name to a new instance or match an existing instance.
    required: True
    default: None
  instance_interfaces:
    description:
      - Assign interfaces to a new instance.
    required: False
    default: []
  instance_raw_config_args:
    description:
      - Additional Vagrant options not explcitly exposed by this module.
    required: False
    default: None
  config_options:
    description:
      - Additional config options not explcitly exposed by this module.
    required: False
    default: {}
  platform_box:
    description:
      - Name of Vagrant box.
    required: True
    default: None
  platform_box_version:
    description:
      - Explicit version of Vagrant box to use.
    required: False
    default: None
  platform_box_url:
    description:
      - The URL to a Vagrant box.
    required: False
    default: None
  provider_name:
    description:
      - Name of the Vagrant provider to use.
    required: False
    default: virtualbox
  provider_memory:
    description:
      - Amount of memory to allocate to the instance.
    required: False
    default: 512
  provider_cpus:
    description:
      - Number of CPUs to allocate to the instance.
    required: False
    default: 2
  provider_options:
    description:
      - Additional provider options not explcitly exposed by this module.
    required: False
    default: {}
  provider_override_args:
    description:
      - Additional override options not explcitly exposed by this module.
    required: False
    default: None
  provider_raw_config_args:
    description:
      - Additional Vagrant options not explcitly exposed by this module.
    required: False
    default: None
  force_stop:
    description:
      - Force halt the instance, then destroy the instance.
    required: False
    default: False
  state:
    description:
      - The desired state of the instance.
    required: True
    choices: ['up', 'halt', 'destroy']
    default: None
  workdir:
    description:
      - vagrant working directory
    required: False
    default: content of MOLECULE_EPHEMERAL_DIRECTORY environment variable
requirements:
    - python >= 2.6
    - python-vagrant
    - vagrant
"""

EXAMPLES = """
See doc/source/configuration.rst
"""

VAGRANTFILE_TEMPLATE = """
{%- macro ruby_format(value) -%}
  {%- if value is boolean -%}
    {{ value | string | lower }}
  {%- elif value is string -%}
    {# "Bug" compat. To be removed later #}
    {%- if value[0] == value[-1] and value.startswith(("'", '"')) -%}
    {{ value }}
    {%- else -%}
    "{{ value }}"
    {%- endif -%}
  {%- else -%}
    {{ value }}
  {%- endif -%}
{%- endmacro -%}

{%- macro dict2args(dictionary) -%}
  {% set sep = joiner(", ") %}
  {%- for key, value in dictionary.items() -%}
    {{ sep() }}{{ key }}: {{ ruby_format(value) }}
  {%- endfor -%}
{%- endmacro -%}

Vagrant.configure('2') do |config|
  if Vagrant.has_plugin?('vagrant-cachier')
    {% if instance.config_options['cachier'] is sameas false %}
    config.cache.disable!
    {% else %}
    config.cache.scope = 'machine'
    {% endif %}
  end

  config.vm.define "{{ instance.name }}" do |c|
    ##
    # Box definition
    ##
    c.vm.box = "{{ instance.box }}"
    {{ 'c.vm.box_version = "{}"'.format(instance.box_version) if instance.box_version }}
    {{ 'c.vm.box_url = "{}"'.format(instance.box_url) if instance.box_url }}

    ##
    # Config options
    ##
    {% if instance.config_options['synced_folder'] is sameas false %}
    c.vm.synced_folder ".", "/vagrant", disabled: true
    {% endif %}

    {% for k,v in instance.config_options.items() %}
    {% if k not in ['synced_folder', 'cachier'] %}c.{{ k }} = {{ ruby_format(v) }}{% endif %}
    {% endfor %}

    c.vm.hostname = "{{ instance.name }}"

    ##
    # Network
    ##
    {% for n in instance.networks %}
    c.vm.network "{{ network.name }}", {{ dict2args(network.options) }}
    {% endfor %}

    ##
    # instance_raw_config_args
    ##
    {% if instance.instance_raw_config_args is not none %}{% for arg in instance.instance_raw_config_args -%}
    c.{{ arg }}
    {% endfor %}{% endif %}

    ##
    # Provider
    ##
    c.vm.provider "{{ instance.provider }}" do |{{ instance.provider | lower }}, override|
      {% if instance.provider.startswith('vmware_') %}
      {{ instance.provider | lower }}.vmx['memsize'] = {{ instance.memory }}
      {{ instance.provider | lower }}.vmx['numvcpus'] = {{ instance.cpus }}
      {% else %}
      {{ instance.provider | lower }}.memory = {{ instance.memory }}
      {{ instance.provider | lower }}.cpus = {{ instance.cpus }}
      {% endif %}

      {% for option, value in instance.provider_options.items() %}
      {{ instance.provider | lower }}.{{ option }} = {{ ruby_format(value) }}
      {% endfor %}

      {% if instance.provider_raw_config_args is not none %}
        {% for arg in instance.provider_raw_config_args %}
      {{ instance.provider | lower }}.{{ arg }}
        {% endfor %}
      {% endif %}

      {% if instance.provider_override_args is not none %}
        {% for arg in instance.provider_override_args -%}
      override.{{ arg }}
        {% endfor %}
      {% endif %}

      {% if instance.provider == 'virtualbox' %}
      {% if 'linked_clone' not in instance.provider_options %}
      virtualbox.linked_clone = true
      {% endif %}
      {% endif %}
      {% if instance.provider == 'libvirt' %}
        {% if 'driver' in instance.provider_options and 'qemu' in instance.provider_options['driver'] %}
          {% if 'cpu_mode' not in instance.provider_options %}
      # When using qemu instead of kvm, some libvirt systems
      # will use EPYC as vCPU model inside the new VM.
      # This will lead to process hang with ssh-keygen -A on alpine.
      # Not sure were the bug is (libvirt or qemu or alpine or all of them) but using QEMU64
      # cpu model will work around this. Hopefully, by checking 'cpu_mode' option, it will
      # allow people to override the model to use.
      libvirt.cpu_mode = 'custom'
      libvirt.cpu_model = 'qemu64'
          {% endif %}
        {% endif %}
      {% endif %}
    end
  end
end
""".strip()  # noqa

RETURN = r"""
rc:
    description: The command return code (0 means success)
    returned: always
    type: int
cmd:
    description: The command executed by the task
    returned: always
    type: str
stdout:
    description: The command standard output
    returned: changed
    type: str
stderr:
    description: Output on stderr
    returned: changed
    type: str
"""


class VagrantClient(object):
    def __init__(self, module):
        self._module = module

        self._config = self._get_config()
        self._vagrantfile = self._config["vagrantfile"]
        self._vagrant = self._get_vagrant()
        self._write_configs()
        self._has_error = None
        self._datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.result = {}

    @contextlib.contextmanager
    def stdout_cm(self):
        """Redirect the stdout to a log file."""
        with open(self._get_stdout_log(), "a+") as fh:
            msg = "### {} ###\n".format(self._datetime)
            fh.write(msg)
            fh.flush()

            yield fh

    @contextlib.contextmanager
    def stderr_cm(self):
        """Redirect the stderr to a log file."""
        with open(self._get_stderr_log(), "a+") as fh:
            msg = "### {} ###\n".format(self._datetime)
            fh.write(msg)
            fh.flush()

            try:
                yield fh
            except subprocess.CalledProcessError as e:
                self._has_error = True
                # msg = "CMD: {} returned {}\n{}".format(
                #     e.cmd, e.returncode, e.output or ""
                # )
                self.result["cmd"] = e.cmd
                self.result["rc"] = e.returncode
                self.result["stderr"] = e.output or ""

                # fh.write(msg)
                # raise
            except Exception as e:
                self._has_error = True
                if hasattr(e, "message"):
                    fh.write(e.message)
                else:
                    fh.write(e)
                fh.flush()
                raise

    def up(self):
        changed = False
        if not self._created():
            changed = True
            provision = self._module.params["provision"]
            try:
                self._vagrant.up(provision=provision)
            except Exception:
                # NOTE(retr0h): Ignore the exception since python-vagrant
                # passes the actual error as a no-argument ContextManager.
                pass

        # NOTE(retr0h): Ansible wants only one module return `fail_json`
        # or `exit_json`.
        if not self._has_error:
            self._module.exit_json(
                changed=changed, log=self._get_stdout_log(), **self._conf()
            )

        msg = "Failed to start the VM: See log file '{}'".format(self._get_stderr_log())
        with io.open(self._get_stderr_log(), "r", encoding="utf-8") as f:
            self.result["stderr"] = f.read()
        self._module.fail_json(msg=msg, **self.result)

    def destroy(self):
        changed = False
        if self._created():
            changed = True
            if self._module.params["force_stop"]:
                self._vagrant.halt(force=True)
            self._vagrant.destroy()

        self._module.exit_json(changed=changed)

    def halt(self):
        changed = False
        if self._created():
            changed = True
            self._vagrant.halt(force=self._module.params["force_stop"])

        self._module.exit_json(changed=changed)

    def _conf(self):
        instance_name = self._module.params["instance_name"]

        try:
            return self._vagrant.conf(vm_name=instance_name)
        except Exception:
            msg = "Failed to get vagrant config for {}: See log file '{}'".format(
                instance_name, self._get_stderr_log()
            )
            with io.open(self._get_stderr_log(), "r", encoding="utf-8") as f:
                self.result["stderr"] = f.read()
                self._module.fail_json(msg=msg, **self.result)

    def _status(self):
        instance_name = self._module.params["instance_name"]
        try:
            s = self._vagrant.status(vm_name=instance_name)[0]

            return {"name": s.name, "state": s.state, "provider": s.provider}
        except Exception:
            msg = "Failed to get status for {}: See log file '{}'".format(
                instance_name, self._get_stderr_log()
            )
            with io.open(self._get_stderr_log(), "r", encoding="utf-8") as f:
                self.result["stderr"] = f.read()
                self._module.fail_json(msg=msg, **self.result)

    def _created(self):
        status = self._status()
        if status and status["state"] == "running":
            return status
        return {}

    def _get_config(self):
        conf = dict()
        conf["workdir"] = os.getenv("MOLECULE_EPHEMERAL_DIRECTORY")
        if self._module.params["workdir"] is not None:
            conf["workdir"] = self._module.params["workdir"]
        conf["vagrantfile"] = os.path.join(conf["workdir"], "Vagrantfile")
        return conf

    def _write_vagrantfile(self):
        template = molecule.util.render_template(
            VAGRANTFILE_TEMPLATE, instance=self._get_vagrant_config_dict()
        )
        molecule.util.write_file(self._vagrantfile, template)

    def _write_configs(self):
        self._write_vagrantfile()
        valid = subprocess.run(
            ["vagrant", "validate"],
            cwd=self._config["workdir"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if valid.returncode != 0:
            self._module.fail_json(
                msg="Failed to validate generated Vagrantfile: {}".format(valid.stderr)
            )

    def _get_vagrant(self):
        v = vagrant.Vagrant(
            out_cm=self.stdout_cm,
            err_cm=self.stderr_cm,
            root=self._config["workdir"],
        )

        return v

    def _get_vagrant_config_dict(self):
        networks = []
        for iface in self._module.params["instance_interfaces"]:
            net = dict()
            net["name"] = iface["network_name"]
            iface.pop("network_name")
            net["options"] = iface
            networks.append(net)

        d = {
            "name": self._module.params["instance_name"],
            "memory": self._module.params["provider_memory"],
            "cpus": self._module.params["provider_cpus"],
            "networks": networks,
            "instance_raw_config_args": self._module.params["instance_raw_config_args"],
            "config_options": {
                # NOTE(retr0h): `synced_folder` does not represent the
                # actual key used by Vagrant.  Is used as a flag to
                # simply enable/disable shared folder.
                "synced_folder": False,
                "ssh.insert_key": True,
                "cachier": True,
            },
            "box": self._module.params["platform_box"],
            "box_version": self._module.params["platform_box_version"],
            "box_url": self._module.params["platform_box_url"],
            "provider": self._module.params["provider_name"],
            "provider_options": {},
            "provider_raw_config_args": self._module.params["provider_raw_config_args"],
            "provider_override_args": self._module.params["provider_override_args"],
        }

        d["config_options"].update(
            molecule.util.merge_dicts(
                d["config_options"], self._module.params["config_options"]
            )
        )

        d["provider_options"].update(
            molecule.util.merge_dicts(
                d["provider_options"], self._module.params["provider_options"]
            )
        )

        return d

    def _get_stdout_log(self):
        return self._get_vagrant_log("out")

    def _get_stderr_log(self):
        return self._get_vagrant_log("err")

    def _get_vagrant_log(self, __type):
        instance_name = self._module.params["instance_name"]

        return os.path.join(
            self._config["workdir"], "vagrant-{}.{}".format(instance_name, __type)
        )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            instance_name=dict(type="str", required=True),
            instance_interfaces=dict(type="list", default=[]),
            instance_raw_config_args=dict(type="list", default=None),
            config_options=dict(type="dict", default={}),
            platform_box=dict(type="str", required=False),
            platform_box_version=dict(type="str"),
            platform_box_url=dict(type="str"),
            provider_name=dict(type="str", default="virtualbox"),
            provider_memory=dict(type="int", default=512),
            provider_cpus=dict(type="int", default=2),
            provider_options=dict(type="dict", default={}),
            provider_override_args=dict(type="list", default=None),
            provider_raw_config_args=dict(type="list", default=None),
            provision=dict(type="bool", default=False),
            force_stop=dict(type="bool", default=False),
            state=dict(type="str", default="up", choices=["up", "destroy", "halt"]),
            workdir=dict(type="str"),
        ),
        supports_check_mode=False,
    )

    v = VagrantClient(module)

    if module.params["state"] == "up":
        v.up()

    if module.params["state"] == "destroy":
        v.destroy()

    if module.params["state"] == "halt":
        v.halt()

    module.fail_json(msg="Unknown error", **v.result)


if __name__ == "__main__":
    main()

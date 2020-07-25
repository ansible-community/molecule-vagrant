#!/usr/bin/python3
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


__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
import contextlib
import datetime
import io
import os
import subprocess
import sys

import molecule
import molecule.config
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
version_added: 2.0
author:
  - Cisco Systems, Inc.
options:
  instances:
    description:
      - List of instances to create. Support options for each instance are:
        - `name`: Name of the instance.
        - `box`: Box to create the instance from.
        - `box_url`: URL to box to create instance from.
        - `box_version`: Box version to use.
        - `cpus`: Number of CPUs to give the instance.
        - `memory`: Amount of memory (in MBs) to give the instance.
        - `synced_folder`: Enables or disables the default /vagrant synced folder.
        - `networks`: List of networks.
        - `config_options`: Dictionary of configuration options.
        - `provider_options`: Dictionary of provider options.
        - `provider_override_args`: List of arguments to override for the provider.
        - `instance_raw_config_args`: List of config arguments.
        - `provider_raw_config_args`: List of provider arguments.
    required: True
    default: None
  provider:
    description:
      - Name of the Vagrant provider to use.
    required: False
    default: virtualbox
  parallel:
    description:
      - Whether to create the instances in parallel.
    required: False
    default: True
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
requirements:
    - python >= 3
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
    "{{ value }}"
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
  {% for instance in instances %}
  config.vm.define "{{ instance.name }}" do |c|
    # Box options
    c.vm.box = "{{ instance.box }}"
    {{ 'c.vm.box_version = "{}"'.format(instance.box_version) if instance.box_version }}
    {{ 'c.vm.box_url = "{}"'.format(instance.box_url) if instance.box_url }}

    c.vm.hostname = "{{ instance.name }}"
    c.vm.synced_folder ".", "/vagrant", nfs_version: 3, disabled: {{ ruby_format(not instance.synced_folder) }}

    # Config options
    {% for key, value in instance.config_options.items() -%}
    c.{{ key }} = {{ ruby_format(value) }}
    {% endfor %}

    # Raw config args
    {% for arg in instance.instance_raw_config_args -%}
    c.{{ arg }}
    {% endfor %}

    # Networking options
    {% for network in instance.networks -%}
    c.vm.network "{{ network.identifier }}", {{ dict2args(network.options) }}
    {% endfor %}

    # Provider options
    c.vm.provider "{{ provider }}" do |provider, override|
      # Set CPUs and memory
      {{ 'provider.{} = {}'.format(cpu_field(provider), instance.cpus) if instance.cpus }}
      {{ 'provider.{} = {}'.format(memory_field(provider), instance.memory) if instance.memory }}

      # General provider options
      {% for option, value in instance.provider_options.items() -%}
      provider.{{ option }} = {{ ruby_format(value) }}
      {% endfor %}

      # Raw provider args
      {% for arg in instance.provider_raw_config_args -%}
      provider.{{ arg }}
      {% endfor %}

      # Raw provider override args
      {% for arg in instance.provider_override_args -%}
      override.{{ arg }}
      {% endfor %}
    end
  end
  {% endfor %}
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


class VagrantClient:
    def __init__(self, module):
        self._module = module

        self._config = self._get_config()
        self._vagrantfile = self._config.driver.vagrantfile
        self._vagrant = self._get_vagrant()
        self._write_vagrantfile()
        self._has_error = None
        self._datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.result = {}

        # Disable parallelism if necessary
        if not self._module.params["parallel"]:
            vagrant_env = os.environ.copy()
            vagrant_env["VAGRANT_NO_PARALLEL"] = "1"
            self._vagrant.env = vagrant_env

    @contextlib.contextmanager
    def stdout_cm(self):
        """ Redirect the stdout to a log file. """
        with open(self._get_stdout_log(), "a+") as fh:
            msg = "### {} ###\n".format(self._datetime)
            fh.write(msg)
            fh.flush()

            yield fh

    @contextlib.contextmanager
    def stderr_cm(self):
        """ Redirect the stderr to a log file. """
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
            try:
                self._vagrant.up(provider=self._module.params["provider"])
            except Exception:
                # NOTE(retr0h): Ignore the exception since python-vagrant
                # passes the actual error as a no-argument ContextManager.
                pass

            # NOTE(retr0h): Ansible wants only one module return `fail_json`
            # or `exit_json`.
            if not self._has_error:
                self._module.exit_json(
                    changed=changed, log=self._get_stdout_log(), results=self._conf()
                )
            else:
                msg = "ERROR: See log file '{}'".format(self._get_stderr_log())
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
        return [
            self._vagrant.conf(vm_name=instance["name"])
            for instance in self._module.params["instances"]
        ]

    def _created(self):
        status = self._vagrant.status()
        if status and all(s.state == "running" for s in status):
            return status
        return {}

    def _get_config(self):
        molecule_file = os.environ["MOLECULE_FILE"]

        return molecule.config.Config(molecule_file)

    def _write_vagrantfile(self):
        # Helper lambdas to get the CPU and memory fields for each provider
        cpu_field = (
            lambda provider: "vmx['numvcpus']"
            if provider.startswith("vmware_")
            else "cpus"
        )
        memory_field = (
            lambda provider: "vmx['memsize']"
            if provider.startswith("vmware_")
            else "memory"
        )

        template = molecule.util.render_template(
            VAGRANTFILE_TEMPLATE,
            cpu_field=cpu_field,
            memory_field=memory_field,
            provider=self._module.params["provider"],
            instances=self._get_vagrant_instances(),
        )
        molecule.util.write_file(self._vagrantfile, template)

    def _get_vagrant(self):
        return vagrant.Vagrant(
            out_cm=self.stdout_cm,
            err_cm=self.stderr_cm,
            root=os.environ["MOLECULE_EPHEMERAL_DIRECTORY"],
        )

    def _get_vagrant_instances(self):
        return [
            {
                "name": instance["name"],
                "box": instance.get("box", "generic/alpine310"),
                "cpus": instance.get("cpus"),
                "memory": instance.get("memory"),
                "box_url": instance.get("box_url"),
                "networks": instance.get("networks", []),
                "box_version": instance.get("box_version"),
                "synced_folder": instance.get("synced_folder", False),
                "config_options": instance.get("config_options", {}),
                "provider_options": instance.get("provider_options", {}),
                "provider_override_args": instance.get("provider_override_args", []),
                "instance_raw_config_args": instance.get(
                    "instance_raw_config_args", []
                ),
                "provider_raw_config_args": instance.get(
                    "provider_raw_config_args", []
                ),
            }
            for instance in self._module.params["instances"]
        ]

    def _get_stdout_log(self):
        return self._get_vagrant_log("out")

    def _get_stderr_log(self):
        return self._get_vagrant_log("err")

    def _get_vagrant_log(self, __type):
        return os.path.join(
            self._config.scenario.ephemeral_directory, "vagrant.{}".format(__type),
        )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            instances=dict(type="list", required=True),
            provider=dict(type="str", default="virtualbox"),
            parallel=dict(type="bool", default=True),
            force_stop=dict(type="bool", default=False),
            state=dict(type="str", default="up", choices=["up", "destroy", "halt"]),
        ),
        supports_check_mode=False,
    )

    vagrant = VagrantClient(module)

    if module.params["state"] == "up":
        vagrant.up()

    if module.params["state"] == "destroy":
        vagrant.destroy()

    if module.params["state"] == "halt":
        vagrant.halt()

    module.exit_json(**module.result)


if __name__ == "__main__":
    main()

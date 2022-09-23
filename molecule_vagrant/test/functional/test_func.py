#  Copyright (c) 2015-2018 Cisco Systems, Inc.
#  Copyright (c) 2018 Red Hat, Inc.
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

import pytest
import os

from molecule import util
from molecule import logger
from molecule.scenario import ephemeral_directory
from molecule.util import run_command
from molecule.test.conftest import change_dir_to

LOG = logger.get_logger(__name__)


def guess_provider():
    prov = None
    toolsdir = os.path.join(
        os.path.dirname(util.abs_path(__file__)),
        os.path.pardir,
        os.path.pardir,
        os.path.pardir,
        "tools",
    )
    result = run_command(["vagrant", "provider"], cwd=toolsdir)
    if result.returncode == 0:
        prov = result.stdout.strip()
    return prov


# @pytest.mark.xfail(reason="need to fix template path")
def test_command_init_scenario(temp_dir):
    with change_dir_to(temp_dir):
        os.makedirs(os.path.join(temp_dir, "molecule", "default"))
        scenario_directory = os.path.join(temp_dir, "molecule", "test-scenario")
        cmd = [
            "molecule",
            "init",
            "scenario",
            "test-scenario",
            "--driver-name",
            "vagrant",
        ]
        result = run_command(cmd)
        assert result.returncode == 0

        assert os.path.isdir(scenario_directory)
        confpath = os.path.join(scenario_directory, "molecule.yml")
        conf = util.safe_load_file(confpath)
        env = os.environ
        if "TESTBOX" in env:
            conf["platforms"][0]["box"] = env["TESTBOX"]
        prov = guess_provider()
        if prov == "libvirt":
            conf["driver"]["provider"] = {"name": "libvirt"}
        util.write_file(confpath, util.safe_dump(conf))

        cmd = ["molecule", "--debug", "test", "-s", "test-scenario"]
        result = run_command(cmd)
        assert result.returncode == 0


def test_invalide_settings(temp_dir):

    scenario_directory = os.path.join(
        os.path.dirname(util.abs_path(__file__)), os.path.pardir, "scenarios"
    )

    with change_dir_to(scenario_directory):
        cmd = ["molecule", "create", "--scenario-name", "invalid"]
        result = run_command(cmd)
        assert result.returncode == 2

        assert "Failed to validate generated Vagrantfile" in result.stdout


def patch_molecule(molecule_yaml):

    conf = util.safe_load_file(molecule_yaml)
    # if provider name set in the molecule.yml means we do care about
    # the provider used, so patch the provider
    if ("provider" in conf["driver"]) and ("name" in conf["driver"]["provider"]):
        curprov = conf["driver"]["provider"]["name"]
        newprov = guess_provider()
        if (newprov is not None) and (curprov != newprov):
            conf["driver"]["provider"]["name"] = newprov
            for i in conf["platforms"]:
                # To specify the nic type, it's default_nic_type in vbox and nic_model_type in libvirt
                # Same for model name (See provider_config_options scenario)
                if "provider_options" in i:
                    if (newprov == "libvirt") and "default_nic_type" in i[
                        "provider_options"
                    ]:
                        i["provider_options"]["nic_model_type"] = "e1000"
                        del i["provider_options"]["default_nic_type"]
            util.write_file(molecule_yaml, util.safe_dump(conf))


@pytest.mark.parametrize(
    "scenario",
    [
        ("vagrant_root"),
        ("config_options"),
        ("provider_config_options"),
        ("provider_config_options2"),
        ("default"),
        ("default-compat"),
        ("network"),
        ("hostname"),
    ],
)
def test_vagrant_root(temp_dir, scenario):

    scenario_directory = os.path.join(
        os.path.dirname(util.abs_path(__file__)), os.path.pardir, "scenarios"
    )

    confpath = os.path.join(scenario_directory, "molecule", scenario, "molecule.yml")
    patch_molecule(confpath)

    with change_dir_to(scenario_directory):
        cmd = ["molecule", "test", "--scenario-name", scenario]
        result = run_command(cmd)
        assert result.returncode == 0


def test_multi_node(temp_dir):

    scenario_directory = os.path.join(
        os.path.dirname(util.abs_path(__file__)), os.path.pardir, "scenarios"
    )

    with change_dir_to(scenario_directory):
        cmd = ["molecule", "test", "--scenario-name", "multi-node"]
        result = run_command(cmd)
        assert result.returncode == 0

    molecule_eph_directory = ephemeral_directory()
    vagrantfile = os.path.join(
        molecule_eph_directory, "scenarios", "multi-node", "Vagrantfile"
    )
    with open(vagrantfile) as f:
        content = f.read()
        assert "instance-1" in content
        assert "instance-2" in content

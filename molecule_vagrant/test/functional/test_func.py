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
from molecule.util import run_command
from molecule.test.conftest import change_dir_to

LOG = logger.get_logger(__name__)


# @pytest.mark.xfail(reason="need to fix template path")
def test_command_init_scenario(temp_dir):
    role_directory = os.path.join(temp_dir.strpath, "test-init")
    cmd = ["molecule", "init", "role", "test-init"]
    result = run_command(cmd)
    assert result.returncode == 0

    with change_dir_to(role_directory):
        molecule_directory = pytest.helpers.molecule_directory()
        scenario_directory = os.path.join(molecule_directory, "test-scenario")
        cmd = [
            "molecule",
            "init",
            "scenario",
            "test-scenario",
            "--role-name",
            "test-init",
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
        if not os.path.exists("/dev/kvm"):
            conf["driver"]["provider"] = {"name": "libvirt"}
            for p in conf["platforms"]:
                p["provider_options"] = {"driver": '"qemu"'}
        util.write_file(confpath, util.safe_dump(conf))

        cmd = ["molecule", "--debug", "test", "-s", "test-scenario"]
        result = run_command(cmd)
        assert result.returncode == 0


@pytest.mark.parametrize(
    "scenario", [("vagrant_root"), ("config_options"), ("provider_config_options")]
)
def test_vagrant_root(temp_dir, scenario):

    env = os.environ
    if not os.path.exists("/dev/kvm"):
        env.update({"VIRT_DRIVER": "'qemu'"})

    scenario_directory = os.path.join(
        os.path.dirname(util.abs_path(__file__)), os.path.pardir, "scenarios"
    )

    with change_dir_to(scenario_directory):
        cmd = ["molecule", "test", "--scenario-name", scenario]
        result = run_command(cmd)
        assert result.returncode == 0

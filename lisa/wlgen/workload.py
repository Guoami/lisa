# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2018, Arm Limited and contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import os
from shlex import quote

from shlex import quote
from datetime import datetime
from devlib.utils.misc import list_to_mask

from lisa.utils import Loggable, ArtifactPath


class Workload(Loggable):
    """
    This is pretty much a wrapper around a command to execute on a target.

    :param target: The Target on which to execute this workload
    :type target: Target

    :param name: Name of the workload. Useful for naming related artefacts.
    :type name: str

    :param res_dir: Directory into which artefacts will be stored
    :type res_dir: str

    :ivar command: The command this workload will execute when invoking
      :meth:`run`. Daughter classes should specify its value before
      :meth:`run` is invoked; preferably in the daughter ``__init__()`` (see
      example below), or in the daughter ``run()`` before the ``super()`` call.

    :ivar output: The saved output of the last :meth:`run()` invocation.

    .. note:: A :class:`Workload` instance can be used as a context manager,
      which ensures :meth:`wipe_run_dir()` is eventually invoked.

    **Design notes**

    ``__init__`` is there to initialize a given workload, and :meth:`run`
    can be called on it several times, with varying arguments.
    As much work as possible should be delegated to :meth:`run`, so that
    different flavours of the same workload can be run without the hassle of
    creating a superfluous amount of new instances. However, when persistent
    data is involved (e.g. the workload depends on a file), then this data
    should be exposed as an ``__init__`` parameter.

    **Implementation example**::

        class Printer(Workload):
            def __init__(self, target, name=None, res_dir=None):
                super().__init__(target, name, res_dir)
                self.command = "echo"

            def run(self, cpus=None, cgroup=None, as_root=False, value=42):
                self.command = "{} {}".format(self.command, shlex.quote(value))
                super().run(cpus, cgroup, as_root)

    **Usage example**::

        >>> printer = Printer(target, "test")
        >>> printer.run()
        INFO    : Printer      : Execution start: echo 42
        INFO    : Printer      : Execution complete
        >>> print printer.output
        42\r\n
    """

    required_tools = ['taskset']
    """
    The tools required to execute the workload. See
    :meth:`lisa.target.Target.install_tools`.
    """

    def __init__(self, target, name=None, res_dir=None):
        self.target = target
        self.name = name or self.__class__.__qualname__
        self.command = None
        self.output = ""

        wlgen_dir = self.target.path.join(target.working_directory,
                                          "lisa", "wlgen")
        target.execute('mkdir -p {}'.format(quote(wlgen_dir)))

        temp_fmt = "{name}_{time}_XXXXXX".format(
            name=self.name.replace('/', '_'),
            time=datetime.now().strftime('%Y%m%d_%H%M%S'),
        )
        cmd = "mktemp -d -p {} {}".format(
            quote(wlgen_dir), quote(temp_fmt)
        )
        self.run_dir = target.execute(cmd).strip()

        self.get_logger().info("Created workload's run target directory: {}".format(self.run_dir))

        res_dir = res_dir if res_dir else target.get_res_dir(
            name='{}{}'.format(
                self.__class__.__qualname__,
                '-{}'.format(name) if name else '')
        )
        self.res_dir = res_dir
        self.target.install_tools(self.required_tools)

    def wipe_run_dir(self):
        """
        Wipe all content from the ``run_dir`` target directory.

        .. note :: This function should only be called directly in interactive
            sessions. For other purposes, use :class:`Workload` instances as a
            context manager.
        """
        logger = self.get_logger()
        logger.info("Wiping target run directory: {}".format(self.run_dir))
        self.target.remove(self.run_dir)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Wipe the run directory on the target.
        """
        self.wipe_run_dir()

    def run(self, cpus=None, cgroup=None, as_root=False, timeout=None):
        """
        Execute the workload on the configured target.

        :param cpus: CPUs on which to restrict the workload execution (taskset)
        :type cpus: list(int)

        :param cgroup: cgroup in which to run the workload
        :type cgroup: str

        :param as_root: Whether to run the workload as root or not
        :type as_root: bool

        :param timeout: Timeout in seconds for the workload execution.
        :type timeout: int

        :raise devlib.exception.TimeoutError: When the specified ``timeout`` is hit.

        The standard output will be saved into a file in ``self.res_dir``
        """
        logger = self.get_logger()
        if not self.command:
            raise RuntimeError("Workload does not specify any command to execute")

        _command = self.command
        target = self.target

        if cpus:
            taskset_bin = target.which('taskset')
            if not taskset_bin:
                raise RuntimeError("Could not find 'taskset' executable on the target")

            cpumask = list_to_mask(cpus)
            taskset_cmd = '{} {}'.format(quote(taskset_bin), quote('0x{:x}'.format(cpumask)))
            _command = '{} {}'.format(taskset_cmd, _command)

        if cgroup:
            _command = target.cgroups.run_into_cmd(cgroup, _command)

        _command = 'cd {} && {}'.format(quote(self.run_dir), _command)

        logger.info("Execution start: {}".format(_command))

        self.output = target.execute(_command, as_root=as_root, timeout=timeout)
        logger.info("Execution complete")

        logfile = ArtifactPath.join(self.res_dir, 'output.log')
        logger.debug('Saving stdout to {}...'.format(logfile))

        with open(logfile, 'w') as ofile:
            ofile.write(self.output)

# vim :set tabstop=4 shiftwidth=4 textwidth=80 expandtab

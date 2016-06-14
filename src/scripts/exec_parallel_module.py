#!/usr/bin/python
# -*- coding: utf-8 -*-
# author:   Jan Hybs
# ----------------------------------------------
import subprocess
import datetime
import time
# ----------------------------------------------
from scripts.core.base import Paths, Printer, Command, IO
from scripts.core.base import PathFormat
from scripts.core.prescriptions import PBSModule
from scripts.core.threads import BinExecutor, PyPy
from scripts.pbs.common import get_pbs_module
from scripts.pbs.job import JobState
from utils.dotdict import Map
# ----------------------------------------------

# global arguments
arg_options = None
arg_others = None
arg_rest = None


def run_local_mode():
    # build command
    mpi_binary = 'mpirun' if arg_options.mpirun else Paths.mpiexec()
    command = [
        mpi_binary,
        '-np', str(arg_options.get('cpu', 1))
    ]
    if arg_options.valgrind:
        valgrind = ['valgrind']
        if type(arg_options.valgrind) is str:
            valgrind.extend(arg_options.valgrind.split())
        # append to command
        command = command + valgrind
    # append rest arguments
    command.extend(arg_rest)

    # prepare executor
    executor = BinExecutor(command)
    pypy = PyPy(executor, progress=not arg_options.batch)

    # set limits
    pypy.limit_monitor.time_limit = arg_options.time_limit
    pypy.limit_monitor.memory_limit = arg_options.memory_limit

    # turn on output
    if arg_options.batch:
        pypy.info_monitor.stdout_stderr = None
    else:
        pypy.info_monitor.stdout_stderr = Paths.temp_file('exec-paral.log')

    # start process
    pypy.start()


def run_pbs_mode():
    # build command
    mpi_binary = 'mpirun' if arg_options.mpirun else Paths.mpiexec()
    command = [
        mpi_binary,
        '-np', str(arg_options.get('cpu', 1))
    ]
    # append rest arguments
    command.extend(arg_rest)

    # get module
    pbs_module = get_pbs_module(arg_options.host)

    # create pbs command
    test_case = Map(
        memory_limit=arg_options.get('memory_limit', None) or 400,
        time_limit=arg_options.get('time_limit', None) or 30
    )
    module = pbs_module.Module(test_case, arg_options.cpu, None)
    temp_file = Paths.temp_file('exec-temp.qsub')
    pbs_command = module.get_pbs_command(arg_options, temp_file)

    # create regular command for execution
    escaped_command = ' '.join(Command.escape_command(command))

    # create pbs script
    pbs_content = PBSModule.format(
        pbs_module.template,
        command=escaped_command,
        root=arg_options.root
    )

    # save pbs script
    IO.write(temp_file, pbs_content)

    # run qsub command
    output = subprocess.check_output(pbs_command)
    start_time = time.time()
    job = pbs_module.ModuleJob.create(output)
    job.update_status()
    Printer.out('Job submitted: {}', job)

    # wait for job to end
    while job.state != JobState.COMPLETED:
        for j in range(6):
            elapsed_str = str(datetime.timedelta(seconds=int(time.time() - start_time)))
            Printer.dyn('Job #{job.id} status: {job.state} ({t})', job=job, t=elapsed_str)

            # test job state
            if job.state == JobState.COMPLETED:
                break

            # sleep for a bit
            time.sleep(0.5)

        # update status every 6 * 0.5 seconds (3 sec update)
        job.update_status()
    Printer.out('\nJob ended')

    # delete tmp file
    IO.delete(temp_file)


def do_work(parser):
    """
    :type parser: utils.argparser.ArgParser
    """

    # parse arguments
    global arg_options, arg_others, arg_rest
    arg_options, arg_others, arg_rest = parser.parse()
    Paths.format = PathFormat.ABSOLUTE

    # check commands
    if not arg_rest:
        parser.exit_usage('No command specified!')

    # run local or pbs mode
    if arg_options.queue:
        Printer.out('Running in PBS mode')
        Printer.separator()
        run_pbs_mode()
    else:
        Printer.out('Running in LOCAL mode')
        Printer.separator()
        run_local_mode()

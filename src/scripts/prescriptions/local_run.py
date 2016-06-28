#!/usr/bin/python
# -*- coding: utf-8 -*-
# author:   Jan Hybs
# ----------------------------------------------
from scripts.core.base import Paths, Printer
from scripts.core.threads import BinExecutor, PyPy, SequentialThreads
from scripts.prescriptions import AbstractRun, CleanThread
from scripts.comparisons import file_comparison
# ----------------------------------------------


class LocalRun(AbstractRun):
    def __init__(self, case):
        super(LocalRun, self).__init__(case)
        self.progress = False

    def create_pypy(self, arg_rest):
        executor = BinExecutor(self.get_command(arg_rest))
        pypy = PyPy(executor)
        pypy.case = self.case

        pypy.limit_monitor.set_limits(self.case)
        pypy.info_monitor.end_fmt = ''
        pypy.info_monitor.start_fmt = 'Running: {}'.format(self.case)

        pypy.progress = self.progress
        pypy.stdout_stderr = Paths.temp_file('runtest-{datetime}.log')
        return pypy

    def create_comparisons(self):
        comparisons = SequentialThreads(name='Comparison', progress=True, indent=True)
        comparisons.thread_name_property = True

        for check_rule in self.case.check_rules:
            method = str(check_rule.keys()[0])
            module = getattr(file_comparison, 'Compare{}'.format(method.capitalize()), None)
            comp_data = check_rule[method]
            if not module:
                Printer.err('Warning! No module for check_rule method "{}"', method)
                continue

            pairs = self._get_ref_output_files(comp_data)
            if pairs:
                for pair in pairs:
                    command = module.get_command(*pair, **comp_data)
                    pm = PyPy(BinExecutor(command), progress=True)

                    # if we fail, set error to 13
                    pm.custom_error = 13
                    pm.info_monitor.active = False
                    pm.limit_monitor.active = False
                    pm.progress_monitor.active = False
                    pm.error_monitor.message = 'Error! Comparison using method {} failed!'.format(method)
                    pm.stdout_stderr = self.case.fs.ndiff_log

                    path = Paths.path_end_until(pair[0], 'ref_output')
                    test_name = Paths.basename(Paths.dirname(Paths.dirname(self.case.fs.ref_output)))
                    size = Paths.filesize(pair[0], True)
                    pm.name = '{}: {} ({})'.format(test_name, path, size)
                    comparisons.add(pm)

        return comparisons
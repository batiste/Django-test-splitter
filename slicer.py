#!/usr/bin/env python
import multiprocessing
import os
import sys
import unittest
from django.test.simple import DjangoTestSuiteRunner
import md5

def deterministic_shuffle(test_list):
    for test in test_list:
        m = md5.new()
        if not hasattr(test, 'id'):
            tid = str(test.__class__)
        else:
            tid = test.id()
        m.update(tid)
        test.hexdigest = m.hexdigest()
    return sorted(test_list, key=lambda test: test.hexdigest)


def run_test_slice(test_labels, extra_tests, slice_index, number_process):
    print "Run test slice %s" % (slice_index)
    runner = DjangoTestSuiteRunnerSlice(slice_index=slice_index,
        number_process=number_process)
    return runner.run_tests(test_labels=test_labels, extra_tests=extra_tests)


class SliceTestRunner(DjangoTestSuiteRunner):

    def run_tests(self, test_labels=None, extra_tests=None):
        pool_size = 4
        print "SliceTestRunner pool size %d" % pool_size
        pool = multiprocessing.Pool(pool_size)
        results = []
        for i in range(0, pool_size):
            results.append(
                pool.apply_async(run_test_slice,
                [test_labels, extra_tests, i, pool_size]))

        for result in results:
            # 15 minutes timeout
            result.get(timeout=15 * 60)

        return []


class DjangoTestSuiteRunnerSlice(DjangoTestSuiteRunner):

    def __init__(self, slice_index, number_process):
        super(DjangoTestSuiteRunnerSlice, self).__init__()
        self.interactive = False
        self.failfast = False
        from django.db import connections, DEFAULT_DB_ALIAS
        for alias in connections:
            connection = connections[alias]
            test_database_name = 'test_slice_' + str(slice_index)
            connection.settings_dict['TEST_NAME'] = test_database_name

        self.slice_index = slice_index
        self.number_process = number_process

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        suite = super(DjangoTestSuiteRunnerSlice, self).build_suite(
            test_labels, extra_tests, **kwargs)
        nb_test_cases = suite.countTestCases()
        share_size = nb_test_cases / float(self.number_process)
        first_pos = int(self.slice_index * share_size)
        last_pos = int(min(nb_test_cases, (self.slice_index + 1) * share_size))
        shuffled = deterministic_shuffle(suite._tests)
        test_slice = shuffled[first_pos:last_pos]
        print("Slice(%d -> %d) on a total of %d tests" % (first_pos, last_pos, nb_test_cases))

        new_suite = unittest.TestSuite()
        for test in test_slice:
            new_suite.addTest(test)

        return new_suite

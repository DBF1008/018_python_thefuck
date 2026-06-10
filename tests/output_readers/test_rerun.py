# -*- encoding: utf-8 -*-

import signal
import pytest
import sys
from mock import Mock, patch
from psutil import AccessDenied, NoSuchProcess, TimeoutExpired

from thefuck.output_readers import rerun


class TestRerun(object):
    def setup_method(self, test_method):
        self.patcher = patch('thefuck.output_readers.rerun.Process')
        self.process_cls_mock = self.patcher.start()
        self.proc_mock = self.process_cls_mock.return_value = Mock()

    def teardown_method(self, test_method):
        self.patcher.stop()

    @patch('thefuck.output_readers.rerun._wait_output', return_value=False)
    @patch('thefuck.output_readers.rerun.Popen')
    def test_get_output_timeout_no_output(self, popen_mock, wait_output_mock):
        popen_mock.return_value.stdout.read.return_value = b''
        assert rerun.get_output('', '') is None
        wait_output_mock.assert_called_once()

    @patch('thefuck.output_readers.rerun._wait_output', return_value=False)
    @patch('thefuck.output_readers.rerun.Popen')
    def test_get_output_timeout_partial_output(self, popen_mock, wait_output_mock):
        popen_mock.return_value.stdout.read.return_value = b'partial'
        assert rerun.get_output('', '') == u'partial'
        wait_output_mock.assert_called_once()

    @patch('thefuck.output_readers.rerun.Popen')
    def test_get_output_invalid_continuation_byte(self, popen_mock):
        output = b'ls: illegal option -- \xc3\nusage: ls [-@ABC...] [file ...]\n'
        expected = u'ls: illegal option -- �\nusage: ls [-@ABC...] [file ...]\n'
        popen_mock.return_value.stdout.read.return_value = output
        actual = rerun.get_output('', '')
        assert actual == expected

    @pytest.mark.skipif(sys.platform == 'win32', reason="skip when running on Windows")
    @patch('thefuck.output_readers.rerun._wait_output')
    def test_get_output_unicode_misspell(self, wait_output_mock):
        rerun.get_output(u'p\xe1cman', u'p\xe1cman')
        wait_output_mock.assert_called_once()

    def test_wait_output_is_slow(self, settings):
        assert rerun._wait_output(Mock(), True)
        self.proc_mock.wait.assert_called_once_with(settings.wait_slow_command)

    def test_wait_output_is_not_slow(self, settings):
        assert rerun._wait_output(Mock(), False)
        self.proc_mock.wait.assert_called_once_with(settings.wait_command)

    @patch('thefuck.output_readers.rerun._kill_process_group')
    @patch('thefuck.output_readers.rerun._kill_process')
    def test_wait_output_timeout(self, kill_process_mock, kill_pg_mock):
        self.proc_mock.wait.side_effect = TimeoutExpired(3)
        self.proc_mock.children.return_value = []
        assert not rerun._wait_output(Mock(), False)
        kill_process_mock.assert_called_once_with(self.proc_mock)

    @patch('thefuck.output_readers.rerun._kill_process_group')
    @patch('thefuck.output_readers.rerun._kill_process')
    def test_wait_output_timeout_children(self, kill_process_mock, kill_pg_mock):
        self.proc_mock.wait.side_effect = TimeoutExpired(3)
        self.proc_mock.children.return_value = [Mock()] * 2
        assert not rerun._wait_output(Mock(), False)
        assert kill_process_mock.call_count == 3

    def test_wait_output_fast_exit(self):
        self.process_cls_mock.side_effect = NoSuchProcess(1)
        assert rerun._wait_output(Mock(), False)

    @patch('thefuck.output_readers.rerun._kill_process_group')
    @patch('thefuck.output_readers.rerun._kill_process')
    def test_wait_output_timeout_children_already_gone(
            self, kill_process_mock, kill_pg_mock):
        self.proc_mock.wait.side_effect = TimeoutExpired(3)
        self.proc_mock.children.side_effect = NoSuchProcess(1)
        assert not rerun._wait_output(Mock(), False)
        kill_process_mock.assert_called_once_with(self.proc_mock)

    def test_kill_process(self):
        proc = Mock()
        rerun._kill_process(proc)
        proc.kill.assert_called_once_with()

    def test_kill_process_no_such_process(self):
        proc = Mock()
        proc.kill.side_effect = NoSuchProcess(1)
        rerun._kill_process(proc)
        proc.kill.assert_called_once_with()

    @patch('thefuck.output_readers.rerun.logs')
    def test_kill_process_access_denied(self, logs_mock):
        proc = Mock()
        proc.kill.side_effect = AccessDenied()
        rerun._kill_process(proc)
        proc.kill.assert_called_once_with()
        logs_mock.debug.assert_called_once()

    @patch('thefuck.output_readers.rerun.os.killpg')
    def test_kill_process_group(self, killpg_mock):
        rerun._kill_process_group(123)
        killpg_mock.assert_called_once_with(123, signal.SIGKILL)

    @patch('thefuck.output_readers.rerun.os.killpg')
    def test_kill_process_group_already_exited(self, killpg_mock):
        killpg_mock.side_effect = OSError()
        rerun._kill_process_group(123)
        killpg_mock.assert_called_once()

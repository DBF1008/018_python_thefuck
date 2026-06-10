import os
import pytest
import tempfile
from mock import patch

from thefuck import const
from thefuck.output_readers import read_log


MARK = const.USER_COMMAND_MARK


class TestGroupByCalls(object):
    def test_single_line_ps1(self, os_environ):
        os_environ['PS1'] = MARK + '$ '
        log = [
            MARK + '$ git push',
            'error: failed to push',
            MARK + '$ ',
        ]
        grouped = list(read_log._group_by_calls(log))
        assert len(grouped) == 2
        assert grouped[0][0] == MARK + '$ git push'
        assert grouped[0][1] == [MARK + '$ git push', 'error: failed to push']
        assert grouped[1][0] == MARK + '$ '

    def test_multiline_ps1_two_lines(self, os_environ):
        os_environ['PS1'] = MARK + 'user@host\n$ '
        log = [
            MARK + 'user@host',
            '$ git push',
            'error: failed to push',
            MARK + 'user@host',
            '$ ',
        ]
        grouped = list(read_log._group_by_calls(log))
        assert len(grouped) == 2
        assert grouped[0][0] == '$ git push'
        assert grouped[0][1] == [
            MARK + 'user@host', '$ git push', 'error: failed to push']
        assert grouped[1][0] == '$ '

    def test_multiline_ps1_three_lines(self, os_environ):
        os_environ['PS1'] = MARK + 'host\\ndir\n$ '
        log = [
            MARK + 'host',
            'dir',
            '$ ls -la',
            'total 0',
            'drwxr-xr-x  2 user user 40 Jan  1 00:00 .',
            MARK + 'host',
            'dir',
            '$ ',
        ]
        grouped = list(read_log._group_by_calls(log))
        assert len(grouped) == 2
        assert grouped[0][0] == '$ ls -la'
        assert grouped[0][1] == [
            MARK + 'host', 'dir', '$ ls -la',
            'total 0', 'drwxr-xr-x  2 user user 40 Jan  1 00:00 .']
        assert grouped[1][0] == '$ '

    def test_repeated_commands(self, os_environ):
        os_environ['PS1'] = MARK + '$ '
        log = [
            MARK + '$ git push',
            'error: push failed A',
            MARK + '$ git push',
            'error: push failed B',
            MARK + '$ ',
        ]
        grouped = list(read_log._group_by_calls(log))
        assert len(grouped) == 3
        assert grouped[0][1] == [MARK + '$ git push', 'error: push failed A']
        assert grouped[1][1] == [MARK + '$ git push', 'error: push failed B']

    def test_empty_log(self, os_environ):
        os_environ['PS1'] = MARK + '$ '
        assert list(read_log._group_by_calls([])) == []

    def test_no_mark_in_log(self, os_environ):
        os_environ['PS1'] = MARK + '$ '
        log = ['some output', 'more output']
        assert list(read_log._group_by_calls(log)) == []

    def test_truncated_multiline_ps1(self, os_environ):
        """PS1 continuation lines cut off at end of log."""
        os_environ['PS1'] = MARK + 'user@host\n$ '
        log = [
            MARK + 'user@host',
            '$ git push',
            'error: failed',
            MARK + 'user@host',
        ]
        grouped = list(read_log._group_by_calls(log))
        assert len(grouped) == 1
        assert grouped[0][0] == '$ git push'

    def test_consecutive_prompts_no_output(self, os_environ):
        os_environ['PS1'] = MARK + '$ '
        log = [
            MARK + '$ ',
            MARK + '$ ',
            MARK + '$ git push',
            'error',
        ]
        grouped = list(read_log._group_by_calls(log))
        assert len(grouped) == 3
        assert grouped[2][0] == MARK + '$ git push'
        assert grouped[2][1] == [MARK + '$ git push', 'error']


class TestGetScriptGroupLines(object):
    def test_finds_last_occurrence(self, os_environ):
        os_environ['PS1'] = MARK + '$ '
        grouped = [
            (MARK + '$ git push', [MARK + '$ git push', 'error A']),
            (MARK + '$ git push', [MARK + '$ git push', 'error B']),
            (MARK + '$ ', [MARK + '$ ']),
        ]
        result = read_log._get_script_group_lines(grouped, 'git push')
        assert result == [MARK + '$ git push', 'error B']

    def test_raises_when_not_found(self):
        grouped = [
            (MARK + '$ ls', [MARK + '$ ls', 'file.txt']),
        ]
        with pytest.raises(read_log.ScriptNotInLog):
            read_log._get_script_group_lines(grouped, 'git push')

    def test_shlex_split_fallback(self):
        grouped = [
            (MARK + "$ echo 'hello", [MARK + "$ echo 'hello", 'output']),
        ]
        result = read_log._get_script_group_lines(grouped, "echo 'hello")
        assert result == [MARK + "$ echo 'hello", 'output']

    def test_empty_script_raises(self):
        with pytest.raises(read_log.ScriptNotInLog):
            read_log._get_script_group_lines([], '')


class TestReadLogData(object):
    def test_small_file(self, os_environ):
        content = (MARK + '$ git push\nerror\n').encode('utf-8')
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            os_environ['THEFUCK_OUTPUT_LOG'] = f.name
        try:
            data = read_log._read_log_data()
            assert MARK + '$ git push' in data
            assert 'error' in data
        finally:
            os.unlink(f.name)

    def test_large_file_reads_tail(self, os_environ):
        filler = b'x' * 80 + b'\n'
        num_filler_lines = (const.LOG_SIZE_IN_BYTES // len(filler)) + 100
        tail_content = MARK + '$ git push\nerror: the real output\n'
        with tempfile.NamedTemporaryFile(delete=False) as f:
            for _ in range(num_filler_lines):
                f.write(filler)
            f.write(tail_content.encode('utf-8'))
            f.flush()
            os_environ['THEFUCK_OUTPUT_LOG'] = f.name
            total_size = f.tell()
        try:
            data = read_log._read_log_data()
            assert 'error: the real output' in data
            assert len(data.encode('utf-8')) < total_size
        finally:
            os.unlink(f.name)

    def test_large_file_skips_partial_first_line(self, os_environ):
        line = b'A' * 200 + b'\n'
        num_lines = (const.LOG_SIZE_IN_BYTES // len(line)) + 10
        with tempfile.NamedTemporaryFile(delete=False) as f:
            for _ in range(num_lines):
                f.write(line)
            f.flush()
            os_environ['THEFUCK_OUTPUT_LOG'] = f.name
        try:
            data = read_log._read_log_data()
            for text_line in data.split('\n'):
                if text_line:
                    assert len(text_line) == 200
        finally:
            os.unlink(f.name)


class TestGetOutput(object):
    @patch('thefuck.output_readers.read_log.pyte')
    def test_returns_none_when_no_log_env(self, pyte_mock, os_environ):
        os_environ['PS1'] = MARK + '$ '
        assert read_log.get_output('git push') is None

    def test_returns_none_when_no_ps1_mark(self, os_environ):
        os_environ['THEFUCK_OUTPUT_LOG'] = '/tmp/fake'
        os_environ['PS1'] = '$ '
        assert read_log.get_output('git push') is None

    def test_returns_none_when_log_missing(self, os_environ):
        os_environ['THEFUCK_OUTPUT_LOG'] = '/tmp/nonexistent_thefuck_log'
        os_environ['PS1'] = MARK + '$ '
        assert read_log.get_output('git push') is None

    def test_returns_none_when_script_not_found(self, os_environ):
        content = (MARK + '$ ls\nfile.txt\n').encode('utf-8')
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            os_environ['THEFUCK_OUTPUT_LOG'] = f.name
        os_environ['PS1'] = MARK + '$ '
        try:
            assert read_log.get_output('git push') is None
        finally:
            os.unlink(f.name)

    def test_full_flow_single_line_ps1(self, os_environ):
        content = (MARK + '$ git push\nerror: failed to push\n'
                   + MARK + '$ \n').encode('utf-8')
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            os_environ['THEFUCK_OUTPUT_LOG'] = f.name
        os_environ['PS1'] = MARK + '$ '
        try:
            output = read_log.get_output('git push')
            assert output is not None
            assert 'error: failed to push' in output
        finally:
            os.unlink(f.name)

    def test_full_flow_multiline_ps1(self, os_environ):
        content = (MARK + 'user@host\n$ git push\nerror: rejected\n'
                   + MARK + 'user@host\n$ \n').encode('utf-8')
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            os_environ['THEFUCK_OUTPUT_LOG'] = f.name
        os_environ['PS1'] = MARK + 'user@host\n$ '
        try:
            output = read_log.get_output('git push')
            assert output is not None
            assert 'error: rejected' in output
        finally:
            os.unlink(f.name)

    def test_full_flow_repeated_commands(self, os_environ):
        content = (MARK + '$ git push\nerror: old\n'
                   + MARK + '$ git push\nerror: latest\n'
                   + MARK + '$ \n').encode('utf-8')
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            os_environ['THEFUCK_OUTPUT_LOG'] = f.name
        os_environ['PS1'] = MARK + '$ '
        try:
            output = read_log.get_output('git push')
            assert output is not None
            assert 'error: latest' in output
            assert 'error: old' not in output
        finally:
            os.unlink(f.name)

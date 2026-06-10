import os
import shlex
import re
try:
    from shutil import get_terminal_size
except ImportError:
    from backports.shutil_get_terminal_size import get_terminal_size
import six
import pyte
from ..exceptions import ScriptNotInLog
from .. import const, logs


def _group_by_calls(log):
    ps1 = os.environ.get('PS1', '')
    ps1_newlines = ps1.count('\\n') + ps1.count('\n')

    script_line = None
    lines = []
    ps1_remaining = 0

    for line in log:
        if const.USER_COMMAND_MARK in line:
            if script_line is not None:
                yield script_line, lines

            ps1_remaining = ps1_newlines
            if ps1_remaining == 0:
                script_line = line
                lines = [line]
            else:
                script_line = None
                lines = [line]
        elif ps1_remaining > 0:
            ps1_remaining -= 1
            lines.append(line)
            if ps1_remaining == 0:
                script_line = line
        elif script_line is not None:
            lines.append(line)

    if script_line is not None:
        yield script_line, lines


def _get_script_group_lines(grouped, script):
    if six.PY2:
        script = script.encode('utf-8')

    try:
        parts = shlex.split(script)
    except ValueError:
        parts = script.split()

    if not parts:
        raise ScriptNotInLog

    for script_line, lines in reversed(grouped):
        if all(part in script_line for part in parts):
            return lines

    raise ScriptNotInLog


def _read_log_data():
    log_path = os.environ['THEFUCK_OUTPUT_LOG']
    size = os.path.getsize(log_path)
    with open(log_path, 'rb') as f:
        if size > const.LOG_SIZE_IN_BYTES:
            f.seek(size - const.LOG_SIZE_IN_BYTES)
            f.readline()
        data = f.read()
    return data.decode('utf-8', errors='replace')


def _get_output_lines(script, data):
    data = re.sub(r'\x00+$', '', data)
    lines = data.split('\n')
    grouped = list(_group_by_calls(lines))
    script_lines = _get_script_group_lines(grouped, script)
    screen = pyte.Screen(get_terminal_size().columns, len(script_lines))
    stream = pyte.Stream(screen)
    stream.feed('\n'.join(script_lines))
    return screen.display


def get_output(script):
    """Reads script output from log.

    :type script: str
    :rtype: str | None

    """
    if six.PY2:
        logs.warn('Experimental instant mode is Python 3+ only')
        return None

    if 'THEFUCK_OUTPUT_LOG' not in os.environ:
        logs.warn("Output log isn't specified")
        return None

    if const.USER_COMMAND_MARK not in os.environ.get('PS1', ''):
        logs.warn(
            "PS1 doesn't contain user command mark, please ensure "
            "that PS1 is not changed after The Fuck alias initialization")
        return None

    try:
        with logs.debug_time(u'Read output from log'):
            data = _read_log_data()
            lines = _get_output_lines(script, data)
            output = '\n'.join(lines).strip()
            logs.debug(u'Received output: {}'.format(output))
            return output
    except OSError:
        logs.warn("Can't read output log")
        return None
    except ScriptNotInLog:
        logs.warn("Script not found in output log")
        return None

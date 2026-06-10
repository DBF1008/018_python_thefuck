import os
import shlex
import signal
import six
from subprocess import Popen, PIPE, STDOUT
from psutil import AccessDenied, NoSuchProcess, Process, TimeoutExpired
from .. import logs
from ..conf import settings


def _kill_process(proc):
    """Tries to kill the process otherwise just logs a debug message, the
    process will be killed when thefuck terminates.

    :type proc: Process

    """
    try:
        proc.kill()
    except NoSuchProcess:
        pass
    except AccessDenied:
        logs.debug(u'Rerun: process PID {} could not be terminated'.format(
            proc.pid))


def _kill_process_group(pgid):
    """Sends SIGKILL to the entire process group, catching races where the
    group has already exited.

    :type pgid: int

    """
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def _wait_output(popen, is_slow):
    """Returns `True` if we can get output of the command in the
    `settings.wait_command` time.

    Command will be killed if it wasn't finished in the time.

    :type popen: Popen
    :rtype: bool

    """
    try:
        proc = Process(popen.pid)
    except NoSuchProcess:
        return True

    try:
        proc.wait(settings.wait_slow_command if is_slow
                  else settings.wait_command)
        return True
    except TimeoutExpired:
        if hasattr(os, 'killpg'):
            _kill_process_group(popen.pid)
        try:
            for child in proc.children(recursive=True):
                _kill_process(child)
        except NoSuchProcess:
            pass
        _kill_process(proc)
        return False


def get_output(script, expanded):
    """Runs the script and obtains stdin/stderr.

    :type script: str
    :type expanded: str
    :rtype: str | None

    """
    env = dict(os.environ)
    env.update(settings.env)

    if six.PY2:
        expanded = expanded.encode('utf-8')

    split_expand = shlex.split(expanded)
    is_slow = split_expand[0] in settings.slow_commands if split_expand else False

    popen_kwargs = dict(shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT,
                        env=env)
    if hasattr(os, 'setsid'):
        popen_kwargs['preexec_fn'] = os.setsid

    with logs.debug_time(u'Call: {}; with env: {}; is slow: {}'.format(
            script, env, is_slow)):
        result = Popen(expanded, **popen_kwargs)
        if _wait_output(result, is_slow):
            output = result.stdout.read().decode('utf-8', errors='replace')
            logs.debug(u'Received output: {}'.format(output))
            return output
        else:
            output = result.stdout.read().decode('utf-8', errors='replace')
            if output:
                logs.debug(u'Received partial output: {}'.format(output))
                return output
            logs.debug(u'Execution timed out!')
            return None

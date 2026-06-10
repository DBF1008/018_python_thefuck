from subprocess import Popen, PIPE
from time import time
import os
from ..utils import DEVNULL, memoize
from .generic import Generic


class Tcsh(Generic):
    friendly_name = 'Tcsh'

    def app_alias(self, alias_name):
        return ("alias {0} 'setenv TF_SHELL tcsh && setenv TF_ALIAS {0} && "
                "set fucked_cmd=`history -h 2 | head -n 1` && "
                "eval `thefuck ${{fucked_cmd}}`'").format(alias_name)

    def _parse_alias(self, alias):
        name, value = alias.split("\t", 1)
        return name, value

    def get_aliases(self):
        current_path = os.environ.get('PATH', '')
        if not memoize.disabled and current_path == self._aliases_cache_path:
            return self._aliases_cache_value

        proc = Popen(['tcsh', '-ic', 'alias'], stdout=PIPE, stderr=DEVNULL)
        result = dict(
            self._parse_alias(alias)
            for alias in proc.stdout.read().decode('utf-8').split('\n')
            if alias and '\t' in alias)

        if not memoize.disabled:
            self._aliases_cache_path = current_path
            self._aliases_cache_value = result
        return result

    _aliases_cache_path = None
    _aliases_cache_value = None

    def _get_history_file_name(self):
        return os.environ.get("HISTFILE",
                              os.path.expanduser('~/.history'))

    def _get_history_line(self, command_script):
        return u'#+{}\n{}\n'.format(int(time()), command_script)

    def how_to_configure(self):
        return self._create_shell_configuration(
            content=u'eval `thefuck --alias`',
            path='~/.tcshrc',
            reload='tcsh')

    def _get_version(self):
        """Returns the version of the current shell"""
        proc = Popen(['tcsh', '--version'], stdout=PIPE, stderr=DEVNULL)
        return proc.stdout.read().decode('utf-8').split()[1]

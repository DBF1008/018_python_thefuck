import pytest
from mock import Mock, patch
from thefuck.entrypoints.fix_command import _get_raw_command


class TestGetRawCommand(object):
    def test_from_force_command_argument(self):
        known_args = Mock(force_command='git brunch')
        assert _get_raw_command(known_args) == ['git brunch']

    def test_from_command_argument(self, os_environ):
        os_environ['TF_HISTORY'] = None
        known_args = Mock(force_command=None,
                          command=['sl'])
        assert _get_raw_command(known_args) == ['sl']

    @pytest.mark.parametrize('history, result', [
        ('git br', 'git br'),
        ('git br\nfcuk', 'git br'),
        ('git br\nfcuk\nls', 'ls'),
        ('git br\nfcuk\nls\nfuk', 'ls')])
    def test_from_history(self, os_environ, history, result):
        os_environ['TF_HISTORY'] = history
        known_args = Mock(force_command=None,
                          command=None)
        assert _get_raw_command(known_args) == [result]

    @pytest.mark.parametrize('history, alias, executables, builtins, result', [
        # executable with args whose name resembles alias — accept via executable check
        ('git push\nfork --flag', 'fuck', ['fork', 'git'], [],
         'fork --flag'),
        # builtin command should be accepted
        ('git push\ncd /tmp', 'fuck', ['git'], ['cd'],
         'cd /tmp'),
        # alias-like typo not in executables/builtins — skip to next
        ('git push\nfcuk', 'fuck', ['git'], ['cd'],
         'git push'),
        # exact alias with args — skip
        ('git push\nfuck --yeah', 'fuck', ['git'], ['cd'],
         'git push'),
        # mixed: alias + typo + builtin + real command
        ('git push\ncd /tmp\nfcuk\nfuck', 'fuck', ['git'], ['cd'],
         'cd /tmp'),
        # executable whose name equals alias similarity threshold — accept via executable
        ('git push\nduck --verbose', 'fuck', ['duck', 'git'], ['cd'],
         'duck --verbose'),
        # non-executable similar to alias with args — skip (not a real command)
        ('git push\nfxck --retry', 'fuck', ['git'], ['cd'],
         'git push'),
    ])
    def test_from_history_with_executables_and_builtins(
            self, os_environ, history, alias, executables,
            builtins, result):
        os_environ['TF_HISTORY'] = history
        os_environ['TF_ALIAS'] = alias
        known_args = Mock(force_command=None, command=None)
        with patch('thefuck.entrypoints.fix_command.get_all_executables',
                   return_value=executables), \
             patch('thefuck.shells.shell.get_builtin_commands',
                   return_value=builtins):
            assert _get_raw_command(known_args) == [result]

# -*- coding: utf-8 -*-

import pytest
from thefuck.shells import Generic


class TestGeneric(object):
    @pytest.fixture
    def shell(self):
        return Generic()

    def test_from_shell(self, shell):
        assert shell.from_shell('pwd') == 'pwd'

    def test_to_shell(self, shell):
        assert shell.to_shell('pwd') == 'pwd'

    def test_and_(self, shell):
        assert shell.and_('ls', 'cd') == 'ls && cd'

    def test_or_(self, shell):
        assert shell.or_('ls', 'cd') == 'ls || cd'

    def test_get_aliases(self, shell):
        assert shell.get_aliases() == {}

    def test_app_alias(self, shell):
        assert 'alias fuck' in shell.app_alias('fuck')
        assert 'alias FUCK' in shell.app_alias('FUCK')
        assert 'thefuck' in shell.app_alias('fuck')
        assert 'TF_ALIAS=fuck PYTHONIOENCODING' in shell.app_alias('fuck')
        assert 'PYTHONIOENCODING=utf-8 thefuck' in shell.app_alias('fuck')

    def test_get_history(self, history_lines, shell):
        history_lines(['ls', 'rm'])
        # We don't know what to do in generic shell with history lines,
        # so just ignore them:
        assert list(shell.get_history()) == []

    def test_split_command(self, shell):
        assert shell.split_command('ls') == ['ls']
        assert shell.split_command(u'echo café') == [u'echo', u'café']

    @pytest.mark.parametrize('command, expected', [
        ('git status ??', ['git', 'status', '??']),
        ('ls file??.txt', ['ls', 'file??.txt']),
        ('ls ??foo ??bar', ['ls', '??foo', '??bar']),
        ('ls file\\ name', ['ls', 'file\\ name']),
        ('ls multiple\\ spaces\\ here', ['ls', 'multiple\\ spaces\\ here']),
        ("ls 'file name'", ['ls', 'file name']),
        ('ls "file name"', ['ls', 'file name']),
        ('ls file\\ name ??', ['ls', 'file\\ name', '??']),
        ('', []),
        ('git log -p', ['git', 'log', '-p']),
        (u'echo éè', [u'echo', u'éè']),
    ])
    def test_split_command_edge_cases(self, shell, command, expected):
        assert shell.split_command(command) == expected

    def test_split_command_unmatched_quote_fallback(self, shell):
        result = shell.split_command("ls 'unmatched")
        assert result == ["ls", "'unmatched"]

    def test_split_command_fallback_preserves_escaped_spaces(self, shell):
        result = shell.split_command("ls file\\ name 'unmatched")
        assert result == ["ls", "file\\ name", "'unmatched"]

    def test_split_command_fallback_filters_empty_parts(self, shell):
        result = shell.split_command("ls  'bad")
        assert result == ["ls", "'bad"]

    def test_how_to_configure(self, shell):
        assert shell.how_to_configure() is None

    @pytest.mark.parametrize('side_effect, expected_info, warn', [
        ([u'3.5.9'], u'Generic Shell 3.5.9', False),
        ([OSError], u'Generic Shell', True),
    ])
    def test_info(self, side_effect, expected_info, warn, shell, mocker):
        warn_mock = mocker.patch('thefuck.shells.generic.warn')
        shell._get_version = mocker.Mock(side_effect=side_effect)
        assert shell.info() == expected_info
        assert warn_mock.called is warn
        assert shell._get_version.called

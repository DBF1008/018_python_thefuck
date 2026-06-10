# -*- coding: utf-8 -*-

import pytest
from tests.utils import Rule, CorrectedCommand
from thefuck import corrector, const
from thefuck.system import Path
from thefuck.types import Command
from thefuck.corrector import get_corrected_commands, organize_commands


@pytest.fixture
def glob(mocker):
    results = {}
    mocker.patch('thefuck.system.Path.glob',
                 new_callable=lambda: lambda *_: results.pop('value', []))
    return lambda value: results.update({'value': value})


class TestGetRules(object):
    @pytest.fixture(autouse=True)
    def load_source(self, monkeypatch):
        monkeypatch.setattr('thefuck.types.load_source',
                            lambda x, _: Rule(x))

    def _compare_names(self, rules, names):
        assert {r.name for r in rules} == set(names)

    @pytest.mark.parametrize('paths, conf_rules, exclude_rules, loaded_rules', [
        (['git.py', 'bash.py'], const.DEFAULT_RULES, [], ['git', 'bash']),
        (['git.py', 'bash.py'], ['git'], [], ['git']),
        (['git.py', 'bash.py'], const.DEFAULT_RULES, ['git'], ['bash']),
        (['git.py', 'bash.py'], ['git'], ['git'], [])])
    def test_get_rules(self, glob, settings, paths, conf_rules, exclude_rules,
                       loaded_rules):
        glob([Path(path) for path in paths])
        settings.update(rules=conf_rules,
                        priority={},
                        exclude_rules=exclude_rules)
        rules = corrector.get_rules()
        self._compare_names(rules, loaded_rules)


def test_get_rules_rule_exception(mocker, glob):
    load_source = mocker.patch('thefuck.types.load_source',
                               side_effect=ImportError("No module named foo..."))
    glob([Path('git.py')])
    assert not corrector.get_rules()
    load_source.assert_called_once_with('git', 'git.py')


def test_get_corrected_commands(mocker):
    command = Command('test', 'test')
    rules = [Rule(match=lambda _: False),
             Rule(match=lambda _: True,
                  get_new_command=lambda x: x.script + '!', priority=100),
             Rule(match=lambda _: True,
                  get_new_command=lambda x: [x.script + '@', x.script + ';'],
                  priority=60)]
    mocker.patch('thefuck.corrector.get_rules', return_value=rules)
    assert ([cmd.script for cmd in get_corrected_commands(command)]
            == ['test!', 'test@', 'test;'])


def test_organize_commands():
    """Ensures that the function removes duplicates and sorts commands."""
    commands = [CorrectedCommand('ls'), CorrectedCommand('ls -la', priority=9000),
                CorrectedCommand('ls -lh', priority=100),
                CorrectedCommand(u'echo café', priority=200),
                CorrectedCommand('ls -lh', priority=9999)]
    assert list(organize_commands(iter(commands))) \
        == [CorrectedCommand('ls'), CorrectedCommand('ls -lh', priority=100),
            CorrectedCommand(u'echo café', priority=200),
            CorrectedCommand('ls -la', priority=9000)]


def test_organize_commands_keeps_lowest_priority():
    """When duplicates appear among non-first commands, keep lowest priority."""
    commands = [CorrectedCommand('git push', priority=100),
                CorrectedCommand('git pull', priority=900),
                CorrectedCommand('git stash', priority=300),
                CorrectedCommand('git pull', priority=200),
                CorrectedCommand('git stash', priority=800)]
    result = list(organize_commands(iter(commands)))
    assert [c.script for c in result] == ['git push', 'git pull', 'git stash']
    assert result[1].priority == 200
    assert result[2].priority == 300


def test_organize_commands_different_side_effects_not_deduped():
    """Same script with different side_effects are distinct candidates."""
    side_effect_a = lambda *_: None
    side_effect_b = lambda *_: None
    commands = [CorrectedCommand('git push', priority=100),
                CorrectedCommand('git push', side_effect=side_effect_a,
                                 priority=200),
                CorrectedCommand('git push', side_effect=side_effect_b,
                                 priority=300)]
    result = list(organize_commands(iter(commands)))
    assert len(result) == 3
    assert result[0].side_effect is None
    assert result[1].side_effect is side_effect_a
    assert result[2].side_effect is side_effect_b


def test_organize_commands_all_duplicates_of_first():
    """When all commands duplicate the first, only the first is yielded."""
    commands = [CorrectedCommand('ls', priority=100),
                CorrectedCommand('ls', priority=200),
                CorrectedCommand('ls', priority=50)]
    result = list(organize_commands(iter(commands)))
    assert len(result) == 1


def test_organize_commands_empty():
    """Empty input yields nothing."""
    assert list(organize_commands(iter([]))) == []
